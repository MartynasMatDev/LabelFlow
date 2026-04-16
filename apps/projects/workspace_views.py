"""Views for the Workspace layer."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Workspace, WorkspaceMember
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
    """Create an organization workspace. Personal ones are auto-created
    on signup, so this form only covers organizations."""
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
            username = request.POST.get('username', '').strip()
            role     = request.POST.get('role', WorkspaceMember.ROLE_MEMBER)
            user = User.objects.filter(username=username).first()
            if not user:
                messages.error(request, f'User "{username}" not found.')
            elif user == workspace.owner:
                messages.warning(request, 'The owner is already part of the workspace.')
            elif WorkspaceMember.objects.filter(workspace=workspace, user=user).exists():
                messages.warning(request, f'{user.username} is already a member.')
            elif role not in dict(WorkspaceMember.ROLE_CHOICES):
                messages.error(request, 'Invalid role.')
            else:
                WorkspaceMember.objects.create(workspace=workspace, user=user, role=role)
                messages.success(request, f'{user.get_full_name() or user.username} added.')

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

    ctx = {
        'active_nav': 'workspace_team',
        'workspace':  workspace,
        'members':    workspace.members.select_related('user').all(),
        'role_choices': WorkspaceMember.ROLE_CHOICES,
    }
    return render(request, 'app/workspace_team.html', ctx)
