from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone

from .models import Project, ProjectMember, ActivityLog, Invitation, Workspace, WorkspaceMember, ProjectAttachment
from .email import send_invitation_email
from .activity import log_activity
from .workspace_utils import get_active_workspace, workspaces_for

from django.db.models import Count, Avg
from apps.images.models import Image, BoundingBox
import os, shutil

def _user_projects(user, include_archived=False, workspace=None):
    """Projects the user can see. If `workspace` is given, limits to that
    workspace; otherwise spans every workspace the user has access to."""
    if workspace is not None:
        if workspace.is_organization:
            qs = Project.objects.filter(workspace=workspace)
        else:
            qs = Project.objects.filter(workspace=workspace, created_by=user)
    else:
        ws_ids = workspaces_for(user).values_list('pk', flat=True)
        qs = Project.objects.filter(
            Q(workspace_id__in=ws_ids)
            | Q(members__user=user)
            | Q(created_by=user)
        ).distinct()
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs


@login_required
def dashboard(request):
    workspace = get_active_workspace(request)
    projects_qs = _user_projects(request.user, workspace=workspace)
    projects = projects_qs.order_by('-updated_at')[:6]
    total_projects = projects_qs.count()
    from apps.images.models import Image
    total_images = Image.objects.filter(project__in=projects_qs).count()

    project_list = []
    for project in projects:
        total = Image.objects.filter(project=project).count()

        annotated = Image.objects.filter(
            project=project,
            status='done'
        ).count()

        project.progress = int((annotated / total) * 100) if total > 0 else 0
        project.total_images = total
        project.annotated_count = annotated

    ctx = {
        'active_nav': 'dashboard',
        'projects': projects,
        'total_projects': total_projects,
        'total_images': total_images,
        'total_members': ProjectMember.objects.filter(
            project__in=projects_qs
        ).values('user').distinct().count(),
    }
    return render(request, 'app/dashboard.html', ctx)


@login_required
def project_list(request):
    workspace = get_active_workspace(request)
    projects = _user_projects(request.user, workspace=workspace)
    ctx = {
        'active_nav': 'projects',
        'projects': projects,
    }
    return render(request, 'app/project_list.html', ctx)


@login_required
def project_create(request):
    active_ws = get_active_workspace(request)
    all_workspaces = workspaces_for(request.user)

    if request.method == 'POST':
        name            = request.POST.get('name', '').strip()
        description     = request.POST.get('description', '').strip()
        annotation_type = request.POST.get('annotation_type', 'bbox')
        workspace_id    = request.POST.get('workspace_id') or (active_ws.pk if active_ws else None)
        planned_image_count = int(request.POST.get('planned_image_count') or 0)

        workspace = None
        if workspace_id:
            workspace = Workspace.objects.filter(pk=workspace_id).first()
            if not workspace or not workspace.user_has_access(request.user):
                messages.error(request, 'Invalid workspace.')
                return render(request, 'app/project_create.html', {
                    'active_nav': 'projects',
                    'workspaces': all_workspaces,
                    'active_workspace': active_ws,
                })

        if not name:
            messages.error(request, 'Project title is required')
            return render(request, 'app/project_create.html', {
                'active_nav': 'projects',
                'workspaces': all_workspaces,
                'active_workspace': active_ws,
            })

        project = Project.objects.create(
            name=name,
            description=description,
            annotation_type=annotation_type,
            planned_image_count=planned_image_count,
            workspace=workspace,
            created_by=request.user,
        )
        ProjectMember.objects.create(project=project, user=request.user, role='admin')
        log_activity(project, request.user, 'project_created', detail=name)
        messages.success(request, f'Project „{name}" created successfully.')
        return redirect('project_list')

    return render(request, 'app/project_create.html', {
        'active_nav': 'projects',
        'workspaces': all_workspaces,
        'active_workspace': active_ws,
    })

def _project_metrics(project):
    images_qs = Image.objects.filter(project=project)

    total_images  = images_qs.count()
    status_counts = images_qs.values('status').annotate(count=Count('id'))
    status_map    = {item['status']: item['count'] for item in status_counts}
    total_boxes   = BoundingBox.objects.filter(image__project=project).count()
    avg_boxes     = BoundingBox.objects.filter(
        image__project=project
    ).values('image').annotate(c=Count('id')).aggregate(avg=Avg('c'))['avg'] or 0
    total_tags    = project.images.values('tags').distinct().count()
    completed     = status_map.get('done', 0)
    progress      = (completed / total_images * 100) if total_images else 0

    # ── Disk usage ──────────────────────────────────────────────────────────
    from django.conf import settings

    # Sum file_size stored on Image rows (fast, no FS access needed)
    from django.db.models import Sum
    from apps.images.models import Image as ImageModel
    total_bytes = (
        ImageModel.objects.filter(project=project)
        .aggregate(s=Sum('file_size'))['s'] or 0
    )

    # Server-wide disk info (the partition where MEDIA_ROOT lives)
    media_root = getattr(settings, 'MEDIA_ROOT', '/')
    try:
        disk       = shutil.disk_usage(media_root)
        disk_total = disk.total
        disk_used  = disk.used
        disk_free  = disk.free
        disk_pct   = round(disk_used / disk_total * 100, 1) if disk_total else 0
    except Exception:
        disk_total = disk_used = disk_free = disk_pct = None

    def fmt_bytes(b):
        if b is None:
            return '—'
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if b < 1024:
                return f'{b:.1f} {unit}'
            b /= 1024
        return f'{b:.1f} PB'

    return {
        'total_images':    total_images,
        'pending':         status_map.get('pending', 0),
        'partial':         status_map.get('partial', 0),
        'done':            completed,
        'total_boxes':     total_boxes,
        'avg_boxes':       round(avg_boxes, 2),
        'total_tags':      total_tags,
        'progress_percent': round(progress, 2),
        'completed_images': completed,
        'remaining_images': max(project.planned_image_count - completed, 0)
                            if project.planned_image_count else None,
        # disk
        'project_disk_bytes': total_bytes,
        'project_disk_human': fmt_bytes(total_bytes),
        'disk_total_human':   fmt_bytes(disk_total),
        'disk_used_human':    fmt_bytes(disk_used),
        'disk_free_human':    fmt_bytes(disk_free),
        'disk_used_pct':      disk_pct,
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

    images_all  = Image.objects.filter(project=project).order_by('name')
    attachments = ProjectAttachment.objects.filter(project=project).select_related('uploaded_by')

    ctx = {
        'active_nav': 'projects',
        'project': project,
        'images': images,
        'images_all': images_all,
        'attachments': attachments,
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
def project_edit(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_is_admin(request.user):
        messages.error(request, 'Only an admin can edit project settings.')
        return redirect('project_detail', project_id=project_id)

    if request.method != 'POST':
        return redirect('project_detail', project_id=project_id)

    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    annotation_type = request.POST.get('annotation_type', '').strip()

    valid_types = [c[0] for c in Project.ANNOTATION_TYPE_CHOICES]
    if not name:
        messages.error(request, 'Project name cannot be empty.')
        return redirect('project_detail', project_id=project_id)
    if annotation_type not in valid_types:
        annotation_type = project.annotation_type

    project.name = name[:200]
    project.description = description
    project.annotation_type = annotation_type
    project.save(update_fields=['name', 'description', 'annotation_type', 'updated_at'])
    log_activity(project, request.user, 'project_created', detail='Project settings updated')
    messages.success(request, 'Project updated.')
    return redirect('project_detail', project_id=project_id)


@login_required
def attachment_upload(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'Access denied.')
        return redirect('project_list')

    if request.method != 'POST':
        return redirect('project_detail', project_id=project_id)

    f = request.FILES.get('attachment_file')
    if not f:
        messages.error(request, 'No file selected.')
        return redirect('project_detail', project_id=project_id)

    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ProjectAttachment.ALLOWED_EXTENSIONS:
        messages.error(request, f'File type "{ext}" not allowed.')
        return redirect('project_detail', project_id=project_id)

    if f.size > ProjectAttachment.MAX_FILE_BYTES:
        messages.error(request, 'File exceeds 20 MB limit.')
        return redirect('project_detail', project_id=project_id)

    description = request.POST.get('attachment_description', '').strip()[:300]

    attachment = ProjectAttachment.objects.create(
        project=project,
        uploaded_by=request.user,
        file=f,
        original_name=f.name,
        file_size=f.size,
        description=description,
    )
    log_activity(project, request.user, 'attachment_uploaded', detail=attachment.original_name)
    messages.success(request, f'"{f.name}" uploaded.')
    return redirect('project_detail', project_id=project_id)


@login_required
def attachment_delete(request, project_id, attachment_id):
    project    = get_object_or_404(Project, id=project_id)
    attachment = get_object_or_404(ProjectAttachment, id=attachment_id, project=project)

    if not project.user_is_admin(request.user) and attachment.uploaded_by != request.user:
        messages.error(request, 'Only an admin or the uploader can delete this file.')
        return redirect('project_detail', project_id=project_id)

    name = attachment.original_name
    attachment.file.delete(save=False)
    attachment.delete()
    log_activity(project, request.user, 'attachment_deleted', detail=name)
    messages.success(request, f'"{name}" deleted.')
    return redirect('project_detail', project_id=project_id)



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

        if action == 'assign_member':
            wm_id = request.POST.get('workspace_member_id')
            role  = request.POST.get('role', 'annotator')
            wm = get_object_or_404(WorkspaceMember, pk=wm_id, workspace=project.workspace)
            if ProjectMember.objects.filter(project=project, user=wm.user).exists():
                messages.warning(request, f'{wm.user.get_full_name() or wm.user.username} is already on this project.')
            else:
                ProjectMember.objects.create(project=project, user=wm.user, role=role)
                log_activity(project, request.user, 'member_added',
                             detail=wm.user.get_full_name() or wm.user.username)
                messages.success(request, f'{wm.user.get_full_name() or wm.user.username} assigned to the project.')

        elif action == 'remove_member':
            member_id  = request.POST.get('member_id')
            membership = get_object_or_404(ProjectMember, id=member_id, project=project)
            if membership.user == project.created_by:
                messages.error(request, 'Cannot remove the project creator.')
            else:
                name = membership.user.get_full_name() or membership.user.username
                membership.delete()
                log_activity(project, request.user, 'member_removed', detail=name)
                messages.success(request, f'{name} removed from the project.')

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
                messages.success(request, 'Role updated.')

        return redirect('team_management', project_id=project.id)

    members = project.members.select_related('user').all()

    # Workspace members not yet assigned to this project (for the assign dropdown)
    assignable = []
    if project.workspace and project.workspace.is_organization:
        assigned_ids = set(members.values_list('user_id', flat=True))
        assigned_ids.add(project.created_by_id)
        assignable = project.workspace.members.select_related('user').exclude(user_id__in=assigned_ids)

    ctx = {
        'active_nav': 'team',
        'project': project,
        'members': members,
        'assignable': assignable,
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


import uuid as _uuid
from django.views.decorators.http import require_POST


@login_required
@require_POST
def share_toggle(request, project_id):
    """Enable, disable, or rotate a public share link for a project."""
    project = get_object_or_404(Project, id=project_id)
    if not project.user_is_admin(request.user):
        messages.error(request, 'Only project admins can manage sharing.')
        return redirect('project_detail', project_id=project.id)

    action = request.POST.get('action', 'enable')
    if action == 'disable':
        project.is_public = False
        project.save(update_fields=['is_public', 'updated_at'])
        messages.success(request, 'Public sharing disabled.')
    elif action == 'rotate':
        project.share_token = _uuid.uuid4()
        project.is_public = True
        project.save(update_fields=['share_token', 'is_public', 'updated_at'])
        messages.success(request, 'New public link generated.')
    else:
        project.is_public = True
        project.save(update_fields=['is_public', 'updated_at'])
        messages.success(request, 'Public sharing enabled.')
    return redirect('project_detail', project_id=project.id)


def public_share_landing(request, share_token):
    """Public landing page for a shared dataset. Shows stats + format download buttons."""
    project = get_object_or_404(
        Project, share_token=share_token, is_public=True, is_archived=False
    )
    images = Image.objects.filter(project=project)
    total = images.count()
    done = images.filter(status='done').count()
    label_names = sorted({
        b.label.name
        for img in images.prefetch_related('bounding_boxes__label', 'polygons__label')
        for b in list(img.bounding_boxes.all()) + list(img.polygons.all())
        if b.label
    })

    ctx = {
        'project': project,
        'image_total': total,
        'image_done': done,
        'label_names': label_names,
    }
    return render(request, 'public_share.html', ctx)


def invitation_prompt(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if invitation.accepted_at is not None:
        messages.info(request, 'This invitation has already been accepted.')
        return redirect('project_detail', project_id=invitation.project.id)
    if invitation.is_expired():
        messages.error(request, 'This invitation has expired.')
        return redirect('dashboard')

    if request.user.is_authenticated:
        if request.user.email.lower() == invitation.email.lower():
            # FIX: guard against duplicate membership before accepting
            if ProjectMember.objects.filter(project=invitation.project, user=request.user).exists():
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=['accepted_at'])
                messages.info(request, f'You are already a member of {invitation.project.name}.')
                return redirect('project_detail', project_id=invitation.project.id)
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

    # FIX: case-insensitive email comparison
    if request.user.email.lower() != invitation.email.lower():
        messages.error(
            request,
            f'This invitation is for {invitation.email}. '
            f'You are logged in as {request.user.email}. '
            'Please log in with the correct account.'
        )
        return redirect('profile')

    # FIX: guard against duplicate membership (e.g. user was added manually
    # between invitation being sent and accepted)
    if ProjectMember.objects.filter(project=invitation.project, user=request.user).exists():
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])
        messages.info(request, f'You are already a member of {invitation.project.name}.')
        return redirect('project_detail', invitation.project.id)

    invitation.accept(request.user)
    log_activity(invitation.project, request.user, 'member_added',
                 detail=request.user.get_full_name() or request.user.username)
    messages.success(request, f'Welcome to {invitation.project.name}!')
    return redirect('project_detail', invitation.project.id)
