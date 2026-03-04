import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from apps.projects.models import Project
from .models import Image
from datetime import datetime

def _user_projects(user):
    return Project.objects.filter(
        Q(members__user=user) | Q(created_by=user)
    ).distinct()


@login_required
def image_list(request, project_id=None):
    project = None
    if project_id:
        project = get_object_or_404(Project, id=project_id)
        if not project.user_has_access(request.user):
            messages.error(request, 'Neturite prieigos prie šio projekto.')
            return redirect('project_list')
        images = Image.objects.filter(project=project)
    else:
        images = Image.objects.filter(project__in=_user_projects(request.user))

    # Filtering
    status_filter = request.GET.get('status', '')
    if status_filter in ('pending', 'partial', 'done'):
        images = images.filter(status=status_filter)

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        images = images.filter(name__icontains=q)

    # Date filtering
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            images = images.filter(uploaded_at__date__gte=sd)
        except ValueError:
            # ignore invalid date
            start_date = ''

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            images = images.filter(uploaded_at__date__lte=ed)
        except ValueError:
            end_date = ''

    # Sort
    sort = request.GET.get('sort', '-uploaded_at')
    if sort in ('name', '-name', 'uploaded_at', '-uploaded_at', 'status'):
        images = images.order_by(sort)

    ctx = {
        'active_nav': 'images',
        'project': project,
        'projects': _user_projects(request.user),
        'images': images,
        'image_count': images.count(),
        'status_filter': status_filter,
        'q': q,
        'sort': sort,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'app/image_list.html', ctx)


@login_required
def image_upload(request):
    projects = _user_projects(request.user)

    if request.method == 'POST':
        project_id = request.POST.get('project')
        project    = get_object_or_404(Project, id=project_id)

        if not project.user_has_access(request.user):
            messages.error(request, 'Neturite prieigos prie šio projekto.')
            return redirect('image_list')

        files = request.FILES.getlist('image_files')
        if not files:
            messages.error(request, 'Nepasirinktas joks failas.')
            return render(request, 'app/image_upload.html', {'projects': projects, 'active_nav': 'images'})

        uploaded = 0
        for f in files:
            # Validate file type
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'):
                messages.warning(request, f'Netinkamas failo tipas: {f.name}')
                continue
            # Validate size (max 20MB)
            if f.size > 20 * 1024 * 1024:
                messages.warning(request, f'Failas per didelis (max 20MB): {f.name}')
                continue

            Image.objects.create(
                project=project,
                uploaded_by=request.user,
                image_file=f,
                name=f.name,
                file_size=f.size,
            )
            uploaded += 1

        if uploaded:
            messages.success(request, f'Įkelta {uploaded} paveikslėlių į projektą „{project.name}".')
        return redirect('project_images', project_id=project.id)

    # Pre-select project from query param
    selected_project_id = request.GET.get('project')
    ctx = {
        'active_nav': 'images',
        'projects': projects,
        'selected_project_id': int(selected_project_id) if selected_project_id else None,
    }
    return render(request, 'app/image_upload.html', ctx)


@login_required
def image_delete(request, image_id):
    image   = get_object_or_404(Image, id=image_id)
    project = image.project
    if not project.user_is_admin(request.user):
        messages.error(request, 'Tik administratorius gali ištrinti paveikslėlius.')
    else:
        image.image_file.delete(save=False)
        image.delete()
        messages.success(request, f'Paveikslėlis „{image.name}" ištrintas.')
    return redirect('project_images', project_id=project.id)

def image_detail(request, pk):
    from .models import Image
    image = Image.objects.get(pk=pk)
    return render(request, "app/image_detail.html", {"image": image})
