from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import Project


def _user_projects(user):
    return Project.objects.filter(
        Q(members__user=user) | Q(created_by=user)
    ).distinct()



@login_required
def project_create(request):
    if request.method == 'POST':
        name            = request.POST.get('name', '').strip()
        description     = request.POST.get('description', '').strip()
        annotation_type = request.POST.get('annotation_type', 'bbox')
        emoji           = request.POST.get('emoji', '◈').strip() or '◈'

        if not name:
            messages.error(request, 'Projekto pavadinimas yra privalomas.')
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
        messages.success(request, f'Projektas „{name}" sukurtas sėkmingai.')
        return redirect('project_list')

    return render(request, 'app/project_create.html', {'active_nav': 'projects'})


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'Neturite prieigos prie šio projekto.')
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
