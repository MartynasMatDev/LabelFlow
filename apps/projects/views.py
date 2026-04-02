from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone

from .models import Project, ProjectMember, ActivityLog, Invitation
from .email import send_invitation_email
from .activity import log_activity

from django.db.models import Count, Avg
from apps.images.models import Image, BoundingBox

def _user_projects(user, include_archived=False):
    qs = Project.objects.filter(
        Q(members__user=user) | Q(created_by=user)
    ).distinct()
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs


@login_required
def dashboard(request):
    projects = _user_projects(request.user).order_by('-updated_at')[:6]
    total_projects = _user_projects(request.user).count()
    from apps.images.models import Image
    total_images = Image.objects.filter(project__in=_user_projects(request.user)).count()
    ctx = {
        'active_nav': 'dashboard',
        'projects': projects,
        'total_projects': total_projects,
        'total_images': total_images,
        'total_members': ProjectMember.objects.filter(
            project__in=_user_projects(request.user)
        ).values('user').distinct().count(),
    }
    return render(request, 'app/dashboard.html', ctx)


@login_required
def project_list(request):
    projects = _user_projects(request.user)
    ctx = {
        'active_nav': 'projects',
        'projects': projects,
    }
    return render(request, 'app/project_list.html', ctx)


@login_required
def project_create(request):
    if request.method == 'POST':
        name            = request.POST.get('name', '').strip()
        description     = request.POST.get('description', '').strip()
        annotation_type = request.POST.get('annotation_type', 'bbox')
        emoji           = request.POST.get('emoji', '◈').strip() or '◈'

        if not name:
            messages.error(request, 'Project title is required')
            return render(request, 'app/project_create.html', {'active_nav': 'projects'})

        project = Project.objects.create(
            name=name,
            description=description,
            annotation_type=annotation_type,
            emoji=emoji,
            created_by=request.user,
        )
        ProjectMember.objects.create(project=project, user=request.user, role='admin')
        log_activity(project, request.user, 'project_created', detail=name)
        messages.success(request, f'Project „{name}" created successfully.')
        return redirect('project_list')

    return render(request, 'app/project_create.html', {'active_nav': 'projects'})

def _project_metrics(project):
    images_qs = Image.objects.filter(project=project)

    total_images = images_qs.count()

    status_counts = images_qs.values('status').annotate(count=Count('id'))
    status_map = {item['status']: item['count'] for item in status_counts}

    total_boxes = BoundingBox.objects.filter(image__project=project).count()

    avg_boxes = BoundingBox.objects.filter(
        image__project=project
    ).values('image').annotate(c=Count('id')).aggregate(avg=Avg('c'))['avg'] or 0

    total_tags = project.images.values('tags').distinct().count()

    return {
        'total_images': total_images,
        'pending': status_map.get('pending', 0),
        'partial': status_map.get('partial', 0),
        'done': status_map.get('done', 0),
        'total_boxes': total_boxes,
        'avg_boxes': round(avg_boxes, 2),
        'total_tags': total_tags,
    }

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')

    from apps.images.models import Image
    images = Image.objects.filter(project=project).order_by('-uploaded_at')[:6]

    activity_qs = ActivityLog.objects.filter(project=project).select_related('user')

    filter_user   = request.GET.get('activity_user', '').strip()
    filter_action = request.GET.get('activity_action', '').strip()

    if filter_user:
        activity_qs = activity_qs.filter(user__username=filter_user)
    if filter_action:
        activity_qs = activity_qs.filter(action=filter_action)

    activity_logs = activity_qs[:50]

    activity_users   = (
        User.objects.filter(activity_logs__project=project)
        .distinct()
        .values_list('username', flat=True)
    )
    activity_actions = ActivityLog.ACTION_CHOICES

    metrics = _project_metrics(project)

    # Images uploaded per user
    images_per_user = (
        Image.objects.filter(project=project)
        .values('uploaded_by__username')
        .annotate(count=Count('id'))
    )

    # Boxes created per user
    boxes_per_user = (
        BoundingBox.objects.filter(image__project=project)
        .values('created_by__username')
        .annotate(count=Count('id'))
    )

    # Annotations completed per user (activity log)
    annotations_done_per_user = (
        ActivityLog.objects.filter(project=project, action='annotation_done')
        .values('user__username')
        .annotate(count=Count('id'))
    )

    # Timeline (images uploaded per day)
    uploads_timeline = (
        Image.objects.filter(project=project)
        .extra({'day': "date(uploaded_at)"})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    ctx = {
        'active_nav': 'projects',
        'project': project,
        'images': images,
        'user_role': project.get_user_role(request.user) or 'admin',
        'is_admin': project.user_is_admin(request.user),
        'metrics': metrics,
        'images_per_user': list(images_per_user),
        'boxes_per_user': list(boxes_per_user),
        'annotations_done_per_user': list(annotations_done_per_user),
        'uploads_timeline': list(uploads_timeline),
        # Activity
        'activity_logs': activity_logs,
        'activity_users': activity_users,
        'activity_actions': activity_actions,
        'filter_user': filter_user,
        'filter_action': filter_action,
    }
    return render(request, 'app/project_detail.html', ctx)


@login_required
def activity_feed_json(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    since_pk = request.GET.get('since')
    qs = ActivityLog.objects.filter(project=project).select_related('user').order_by('-created_at')
    if since_pk:
        qs = qs.filter(pk__gt=since_pk)
    qs = qs[:50]

    data = []
    for entry in qs:
        data.append({
            'id':          entry.pk,
            'actor':       entry.actor_name,
            'initials':    entry.get_initials(),
            'action':      entry.get_action_display(),
            'action_key':  entry.action,
            'detail':      entry.detail,
            'icon':        entry.icon,
            'color':       entry.color_class,
            'timestamp':   entry.created_at.strftime('%Y-%m-%d %H:%M'),
            'iso':         entry.created_at.isoformat(),
        })

    return JsonResponse({'activities': data})


@login_required
def team_management(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if not project.user_is_admin(request.user):
        messages.error(request, 'Only admins can manage this project.')
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_member':
            username = request.POST.get('username', '').strip()
            role     = request.POST.get('role', 'annotator')
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                messages.error(request, f'User "{username}" not found.')
                return redirect('team_management', project_id=project.id)

            if ProjectMember.objects.filter(project=project, user=user).exists():
                messages.warning(request, f'{user.username} is already a member of this project.')
            else:
                ProjectMember.objects.create(project=project, user=user, role=role)
                log_activity(project, request.user, 'member_added',
                             detail=user.get_full_name() or user.username)
                messages.success(request, f'{user.get_full_name() or user.username} added to the team.')

        elif action == 'remove_member':
            member_id  = request.POST.get('member_id')
            membership = get_object_or_404(ProjectMember, id=member_id, project=project)
            if membership.user == project.created_by:
                messages.error(request, 'Cannot remove the project creator.')
            else:
                name = membership.user.get_full_name() or membership.user.username
                membership.delete()
                log_activity(project, request.user, 'member_removed', detail=name)
                messages.success(request, f'{name} has been removed from the team.')

        elif action == 'change_role':
            member_id = request.POST.get('member_id')
            new_role  = request.POST.get('role')
            membership = get_object_or_404(ProjectMember, id=member_id, project=project)
            if new_role in dict(ProjectMember.ROLE_CHOICES):
                old_role = membership.get_role_display()
                membership.role = new_role
                membership.save()
                name = membership.user.get_full_name() or membership.user.username
                log_activity(project, request.user, 'role_changed',
                             detail=f'{name}: {old_role} → {membership.get_role_display()}')
                messages.success(request, 'Role updated successfully.')

        elif action == 'send_invitation':
            email = request.POST.get('email', '').strip()
            role = request.POST.get('role', 'annotator')
            # Validate email
            if not email:
                messages.error(request, 'Email address is required.')
                return redirect('team_management', project_id=project.id)
            # Check if email is already a member
            user_exists = User.objects.filter(email=email).first()
            if user_exists and ProjectMember.objects.filter(project=project, user=user_exists).exists():
                messages.error(request, f'{email} is already a member of this project.')
                return redirect('team_management', project_id=project.id)
            # Check for pending invitation
            if Invitation.objects.filter(project=project, email=email, accepted_at__isnull=True).exists():
                messages.warning(request, f'An invitation has already been sent to {email}.')
                return redirect('team_management', project_id=project.id)
            # Create invitation
            invitation = Invitation.objects.create(
                project=project,
                email=email,
                invited_by=request.user,
                role=role,
                expires_at=timezone.now() + timezone.timedelta(days=7)  # expire after 7 days
            )
            # Send email
            try:
                send_invitation_email(invitation)
                messages.success(request, f'Invitation sent to {email}.')
            except Exception as e:
                messages.warning(request, f'Invitation created but email could not be sent: {str(e)}')
            return redirect('team_management', project_id=project.id)

        elif action == 'cancel_invitation':
            invitation_id = request.POST.get('invitation_id')
            try:
                inv = Invitation.objects.get(id=invitation_id, project=project)
                inv.delete()
                messages.success(request, f'Invitation to {inv.email} cancelled.')
            except Invitation.DoesNotExist:
                messages.error(request, 'Invitation not found.')

        return redirect('team_management', project_id=project.id)

    members = project.members.select_related('user').all()
    pending_invitations = project.invitations.filter(accepted_at__isnull=True)

    ctx = {
        'active_nav': 'team',
        'project': project,
        'members': members,
        'pending_invitations': pending_invitations,
        'role_choices': ProjectMember.ROLE_CHOICES,
    }
    return render(request, 'app/team_management.html', ctx)


@login_required
def archived_projects(request):
    projects = _user_projects(request.user, include_archived=True).filter(is_archived=True)
    projects = [p for p in projects if p.user_is_admin(request.user)]
    return render(request, 'app/archived_projects.html', {
        'active_nav': 'projects',
        'projects': projects,
    })


@login_required
def archive_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_is_admin(request.user):
        messages.error(request, 'Only admins can archive projects.')
        return redirect('project_detail', project_id=project.id)
    project.archive()
    log_activity(project, request.user, 'project_archived', detail=project.name)
    messages.success(request, f'Project "{project.name}" archived.')
    return redirect('project_list')


@login_required
def restore_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_is_admin(request.user):
        messages.error(request, 'Only admins can restore projects.')
        return redirect('project_detail', project_id=project.id)
    project.restore()
    log_activity(project, request.user, 'project_restored', detail=project.name)
    messages.success(request, f'Project "{project.name}" restored.')
    return redirect('archived_projects')


def invitation_prompt(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if invitation.accepted_at is not None:
        messages.info(request, 'This invitation has already been accepted.')
        return redirect('project_detail', project_id=invitation.project.id)
    if invitation.is_expired():
        messages.error(request, 'This invitation has expired.')
        return redirect('dashboard')

    if request.user.is_authenticated:
        if request.user.email == invitation.email:
            # Accept and redirect
            invitation.accept(request.user)
            log_activity(invitation.project, request.user, 'member_added',
                         detail=request.user.get_full_name() or request.user.username)
            messages.success(request, f'You have been added to {invitation.project.name} as a {invitation.get_role_display()}.')
            return redirect('project_detail', project_id=invitation.project.id)
        else:
            messages.error(request, f'This invitation is for {invitation.email}. Please log out and log in with that account.')
            return redirect('profile')

    # Not logged in: show prompt with links to login/register
    ctx = {
        'invitation': invitation,
        'login_url': reverse('login') + f'?next={reverse("accept_invitation", args=[token])}',
        'register_url': reverse('register') + f'?next={reverse("accept_invitation", args=[token])}',
    }
    return render(request, 'app/invitation_prompt.html', ctx)


@login_required
def accept_invitation(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if invitation.accepted_at:
        messages.info(request, 'Invitation already accepted.')
        return redirect('project_detail', invitation.project.id)
    if invitation.is_expired():
        messages.error(request, 'Invitation expired.')
        return redirect('dashboard')

    if request.user.email != invitation.email:
        messages.error(request, f'This invitation is for {invitation.email}. Please log out and log in with that account.')
        return redirect('profile')

    invitation.accept(request.user)
    log_activity(invitation.project, request.user, 'member_added',
                 detail=request.user.get_full_name() or request.user.username)
    messages.success(request, f'Welcome to {invitation.project.name}!')
    return redirect('project_detail', invitation.project.id)