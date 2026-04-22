"""Views for the Workspace layer."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .email import send_workspace_invitation_email
from .models import Workspace, WorkspaceMember, WorkspaceInvitation
from .workspace_utils import (
    get_active_workspace,
    set_active_workspace,
    workspaces_for,
)


@login_required
def workspace_list(request):
    workspaces = workspaces_for(request.user).prefetch_related('projects')
    active = get_active_workspace(request)
    ctx = {
        'active_nav': 'workspaces',
        'workspaces': workspaces,
        'active_workspace': active,
    }
    return render(request, 'app/workspace_list.html', ctx)


@login_required
def workspace_create(request):
    """Create an organization workspace. Personal ones are auto-created on signup."""
    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        emoji       = request.POST.get('emoji', '◈').strip() or '◈'

        if not name:
            messages.error(request, 'Workspace name is required.')
            return render(request, 'app/workspace_create.html', {'active_nav': 'workspaces'})

        workspace = Workspace.objects.create(
            name=name,
            description=description,
            kind=Workspace.KIND_ORGANIZATION,
            owner=request.user,
            emoji=emoji,
        )
        set_active_workspace(request, workspace)
        messages.success(request, f'Workspace "{workspace.name}" created.')
        return redirect('workspace_detail', workspace_id=workspace.pk)

    return render(request, 'app/workspace_create.html', {'active_nav': 'workspaces'})


@login_required
def workspace_detail(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    if not workspace.user_has_access(request.user):
        messages.error(request, 'You do not have access to this workspace.')
        return redirect('workspace_list')

    projects = workspace.projects.filter(is_archived=False).order_by('-updated_at')
    ctx = {
        'active_nav': 'workspaces',
        'workspace': workspace,
        'projects': projects,
        'is_admin':  workspace.user_is_admin(request.user),
    }
    return render(request, 'app/workspace_detail.html', ctx)


@login_required
def workspace_switch(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    if not workspace.user_has_access(request.user):
        return HttpResponseForbidden('No access to that workspace.')
    set_active_workspace(request, workspace)
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or reverse('dashboard')
    return redirect(next_url)


@login_required
def workspace_team(request, workspace_id):
    """Manage membership on an organization workspace."""
    workspace = get_object_or_404(Workspace, pk=workspace_id)

    if workspace.is_personal:
        messages.info(request, 'Personal workspaces do not have team members.')
        return redirect('workspace_detail', workspace_id=workspace.pk)

    if not workspace.user_is_admin(request.user):
        messages.error(request, 'Only workspace admins can manage the team.')
        return redirect('workspace_detail', workspace_id=workspace.pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_member':
            email = request.POST.get('email', '').strip().lower()
            role  = request.POST.get('role', WorkspaceMember.ROLE_MEMBER)

            if not email:
                messages.error(request, 'Email address is required.')
            elif role not in dict(WorkspaceMember.ROLE_CHOICES):
                messages.error(request, 'Invalid role.')
            else:
                user = User.objects.filter(email__iexact=email).first()
                if user:
                    if user == workspace.owner:
                        messages.warning(request, 'The owner is already part of the workspace.')
                    elif WorkspaceMember.objects.filter(workspace=workspace, user=user).exists():
                        messages.warning(request, f'{email} is already a member.')
                    else:
                        WorkspaceMember.objects.create(workspace=workspace, user=user, role=role)
                        messages.success(request, f'{user.get_full_name() or user.username} added to the workspace.')
                else:
                    # User doesn't exist — send invitation
                    if WorkspaceInvitation.objects.filter(workspace=workspace, email=email, accepted_at__isnull=True).exists():
                        messages.warning(request, f'An invitation has already been sent to {email}.')
                    else:
                        invitation = WorkspaceInvitation.objects.create(
                            workspace=workspace,
                            email=email,
                            invited_by=request.user,
                            role=role,
                            expires_at=timezone.now() + timezone.timedelta(days=7),
                        )
                        try:
                            send_workspace_invitation_email(invitation)
                            messages.success(request, f'Invitation sent to {email}.')
                        except Exception as e:
                            messages.warning(request, f'Invitation created but email could not be sent: {e}')

        elif action == 'cancel_invitation':
            inv_id = request.POST.get('invitation_id')
            try:
                inv = WorkspaceInvitation.objects.get(pk=inv_id, workspace=workspace)
                email = inv.email
                inv.delete()
                messages.success(request, f'Invitation to {email} cancelled.')
            except WorkspaceInvitation.DoesNotExist:
                messages.error(request, 'Invitation not found.')

        elif action == 'remove_member':
            member_id = request.POST.get('member_id')
            membership = get_object_or_404(WorkspaceMember, pk=member_id, workspace=workspace)
            name = membership.user.get_full_name() or membership.user.username
            membership.delete()
            messages.success(request, f'{name} removed from the workspace.')

        elif action == 'change_role':
            member_id = request.POST.get('member_id')
            new_role  = request.POST.get('role')
            membership = get_object_or_404(WorkspaceMember, pk=member_id, workspace=workspace)
            if new_role in dict(WorkspaceMember.ROLE_CHOICES):
                membership.role = new_role
                membership.save(update_fields=['role'])
                messages.success(request, 'Role updated.')

        return redirect('workspace_team', workspace_id=workspace.pk)

    projects = workspace.projects.filter(is_archived=False).order_by('name')
    pending_invitations = workspace.invitations.filter(accepted_at__isnull=True)

    ctx = {
        'active_nav': 'workspace_team',
        'workspace':  workspace,
        'members':    workspace.members.select_related('user').all(),
        'role_choices': WorkspaceMember.ROLE_CHOICES,
        'pending_invitations': pending_invitations,
        'projects': projects,
    }
    return render(request, 'app/workspace_team.html', ctx)


def workspace_invitation_prompt(request, token):
    invitation = get_object_or_404(WorkspaceInvitation, token=token)

    if invitation.accepted_at is not None:
        messages.info(request, 'This invitation has already been accepted.')
        return redirect('workspace_detail', workspace_id=invitation.workspace.pk)
    if invitation.is_expired():
        messages.error(request, 'This invitation has expired.')
        return redirect('dashboard')

    if request.user.is_authenticated:
        if request.user.email.lower() == invitation.email.lower():
            if WorkspaceMember.objects.filter(workspace=invitation.workspace, user=request.user).exists():
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=['accepted_at'])
                messages.info(request, f'You are already a member of {invitation.workspace.name}.')
                return redirect('workspace_detail', workspace_id=invitation.workspace.pk)
            invitation.accept(request.user)
            messages.success(request, f'You have joined {invitation.workspace.name} as {invitation.get_role_display()}.')
            return redirect('workspace_detail', workspace_id=invitation.workspace.pk)
        else:
            messages.error(request, f'This invitation is for {invitation.email}. Please log in with that account.')
            return redirect('profile')

    ctx = {
        'invitation': invitation,
        'login_url':    reverse('login')    + f'?next={reverse("accept_workspace_invitation", args=[token])}',
        'register_url': reverse('register') + f'?next={reverse("accept_workspace_invitation", args=[token])}',
    }
    return render(request, 'app/workspace_invitation_prompt.html', ctx)


@login_required
def accept_workspace_invitation(request, token):
    invitation = get_object_or_404(WorkspaceInvitation, token=token)

    if invitation.accepted_at:
        messages.info(request, 'Invitation already accepted.')
        return redirect('workspace_detail', workspace_id=invitation.workspace.pk)
    if invitation.is_expired():
        messages.error(request, 'Invitation expired.')
        return redirect('dashboard')

    if request.user.email.lower() != invitation.email.lower():
        messages.error(
            request,
            f'This invitation is for {invitation.email}. '
            f'You are logged in as {request.user.email}.'
        )
        return redirect('profile')

    if WorkspaceMember.objects.filter(workspace=invitation.workspace, user=request.user).exists():
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])
        messages.info(request, f'You are already a member of {invitation.workspace.name}.')
        return redirect('workspace_detail', workspace_id=invitation.workspace.pk)

    invitation.accept(request.user)
    messages.success(request, f'Welcome to {invitation.workspace.name}!')
    return redirect('workspace_detail', workspace_id=invitation.workspace.pk)
