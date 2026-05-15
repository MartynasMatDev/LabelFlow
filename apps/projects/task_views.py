"""Views for task management."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.contrib.auth.models import User  # Add this import
from django.db import models as db_models
import json

from .models import Project, ProjectMember
from .task_models import Task, TaskComment
from .workspace_utils import get_active_workspace, workspaces_for


@login_required
def project_tasks(request, project_id):
    """View all tasks for a project."""
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    assigned_to_filter = request.GET.get('assigned_to', '')

    tasks = Task.objects.filter(project=project)

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if assigned_to_filter:
        tasks = tasks.filter(assigned_to_id=assigned_to_filter)

    # Get project members for filter dropdown
    members = project.members.select_related('user').all()
    member_list = [{'id': m.user.id, 'name': m.user.get_full_name() or m.user.username}
                   for m in members]
    # Add project creator if not already in members
    if project.created_by_id not in [m['id'] for m in member_list]:
        member_list.insert(0, {'id': project.created_by.id, 'name': project.created_by.get_full_name() or project.created_by.username})

    ctx = {
        'active_nav': 'tasks',
        'project': project,
        'tasks': tasks,
        'members': member_list,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assigned_to_filter': assigned_to_filter,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
        'is_admin': project.user_is_admin(request.user),
    }
    return render(request, 'app/project_tasks.html', ctx)


@login_required
@require_http_methods(['GET', 'POST'])
def task_detail(request, project_id, task_id):
    """View and edit a specific task."""
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)

    task = get_object_or_404(Task, id=task_id, project=project)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            if action == 'update_status':
                new_status = data.get('status')
                if new_status in dict(Task.STATUS_CHOICES):
                    task.status = new_status
                    if new_status == 'completed':
                        task.completed_at = timezone.now()
                    task.save()
                    return JsonResponse({'success': True, 'status': task.status})

            elif action == 'update_priority':
                new_priority = data.get('priority')
                if new_priority in dict(Task.PRIORITY_CHOICES):
                    task.priority = new_priority
                    task.save()
                    return JsonResponse({'success': True, 'priority': task.priority})

            elif action == 'add_comment':
                body = data.get('body', '').strip()
                if body:
                    comment = TaskComment.objects.create(
                        task=task,
                        author=request.user,
                        body=body
                    )
                    return JsonResponse({'success': True, 'comment': comment.to_dict()})

            elif action == 'update_task':
                if 'title' in data:
                    task.title = data.get('title', task.title)
                if 'description' in data:
                    task.description = data.get('description', task.description)
                if data.get('due_date'):
                    task.due_date = timezone.datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
                task.save()
                return JsonResponse({'success': True, 'task': task.to_dict()})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # GET request - return task data as JSON
    task_dict = task.to_dict()
    comments = [c.to_dict() for c in task.comments.all()]
    task_dict['comments'] = comments
    return JsonResponse({'task': task_dict})


@login_required
@require_POST
def task_create(request, project_id):
    """Create a new task."""
    project = get_object_or_404(Project, id=project_id)
    if not project.user_is_admin(request.user):
        return JsonResponse({'error': 'Only admins can create tasks'}, status=403)

    try:
        data = json.loads(request.body)

        assigned_to_id = data.get('assigned_to')
        assigned_to = get_object_or_404(User, id=assigned_to_id)

        # Verify assigned user is a project member
        if not ProjectMember.objects.filter(project=project, user=assigned_to).exists() and assigned_to != project.created_by:
            return JsonResponse({'error': 'User is not a project member'}, status=400)

        task = Task.objects.create(
            project=project,
            title=data.get('title', ''),
            description=data.get('description', ''),
            assigned_to=assigned_to,
            assigned_by=request.user,
            priority=data.get('priority', 'medium'),
            due_date=timezone.datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')) if data.get('due_date') else None,
        )

        return JsonResponse({'success': True, 'task': task.to_dict()})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def task_delete(request, project_id, task_id):
    """Delete a task."""
    project = get_object_or_404(Project, id=project_id)
    if not project.user_is_admin(request.user):
        return JsonResponse({'error': 'Only admins can delete tasks'}, status=403)

    task = get_object_or_404(Task, id=task_id, project=project)
    task.delete()

    return JsonResponse({'success': True})


@login_required
def my_tasks(request):
    """View tasks assigned to the current user across all accessible projects."""
    # Get projects user has access to
    ws_ids = workspaces_for(request.user).values_list('pk', flat=True)
    projects = Project.objects.filter(
        db_models.Q(workspace_id__in=ws_ids) |
        db_models.Q(members__user=request.user) |
        db_models.Q(created_by=request.user)
    ).distinct()

    tasks = Task.objects.filter(project__in=projects, assigned_to=request.user)

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    ctx = {
        'active_nav': 'my_tasks',
        'tasks': tasks,
        'status_filter': status_filter,
        'status_choices': Task.STATUS_CHOICES,
    }
    return render(request, 'app/my_tasks.html', ctx)