from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import Project, ProjectMember


def _user_projects(user):
    return Project.objects.filter(
        Q(members__user=user) | Q(created_by=user)
    ).distinct()


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
        'total_members': ProjectMember.objects.filter(project__in=_user_projects(request.user)).values('user').distinct().count(),
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
        # Auto-add creator as admin
        ProjectMember.objects.create(project=project, user=request.user, role='admin')
        messages.success(request, f'Project „{name}" created successfully.')
        return redirect('project_list')

    return render(request, 'app/project_create.html', {'active_nav': 'projects'})


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')
    from apps.images.models import Image
    images = Image.objects.filter(project=project).order_by('-uploaded_at')[:6]
    ctx = {
        'active_nav': 'projects',
        'project': project,
        'images': images,
        'user_role': project.get_user_role(request.user) or 'admin',
        'is_admin': project.user_is_admin(request.user),
    }
    return render(request, 'app/project_detail.html', ctx)


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
                if user == request.user:
                    messages.warning(request, 'You are already a member of this project.')
                else:
                    _, created = ProjectMember.objects.get_or_create(
                        project=project, user=user,
                        defaults={'role': role}
                    )
                    if created:
                        messages.success(request, f'Member {user.get_full_name() or user.username} added.')
                    else:
                        messages.warning(request, f'{user.username} jis already member of this project')
            except User.DoesNotExist:
                messages.error(request, f'User „{username}" not found.')

        elif action == 'remove_member':
            member_id = request.POST.get('member_id')
            membership = get_object_or_404(ProjectMember, id=member_id, project=project)
            if membership.user == project.created_by:
                messages.error(request, 'Cannot remove creator from this project.')
            else:
                name = membership.user.get_full_name() or membership.user.username
                membership.delete()
                messages.success(request, f'Narys {name} pašalintas.')

        elif action == 'change_role':
            member_id = request.POST.get('member_id')
            new_role  = request.POST.get('role')
            membership = get_object_or_404(ProjectMember, id=member_id, project=project)
            if new_role in dict(ProjectMember.ROLE_CHOICES):
                membership.role = new_role
                membership.save()
                messages.success(request, 'Role updated successfully.')

        return redirect('team_management', project_id=project.id)

    members = project.members.select_related('user').all()
    ctx = {
        'active_nav': 'team',
        'project': project,
        'members': members,
        'role_choices': ProjectMember.ROLE_CHOICES,
    }
    return render(request, 'app/team_management.html', ctx)
