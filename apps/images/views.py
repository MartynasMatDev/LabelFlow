import os
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST

from apps.projects.models import Project
from .models import Image, Tag


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


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
            messages.error(request, 'You do not have access to this project.')
            return redirect('project_list')
        images = Image.objects.filter(project=project)
    else:
        images = Image.objects.filter(project__in=_user_projects(request.user))

    # Filtering
    status_filter = request.GET.get('status', '')
    if status_filter in ('pending', 'partial', 'done'):
        images = images.filter(status=status_filter)

    # Tag filter
    tag_filter = request.GET.get('tag', '')
    if tag_filter:
        images = images.filter(tags__id=tag_filter)

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

    all_tags = Tag.objects.all()

    ctx = {
        'active_nav': 'images',
        'project': project,
        'projects': _user_projects(request.user),
        'images': images,
        'image_count': images.count(),
        'status_filter': status_filter,
        'tag_filter': tag_filter,
        'all_tags': all_tags,
        'q': q,
        'sort': sort,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'app/image_list.html', ctx)


@login_required
def image_upload(request):
    """Classic multi-file upload (form POST) — unchanged behaviour."""
    projects = _user_projects(request.user)

    if request.method == 'POST':
        project_id = request.POST.get('project')
        project = get_object_or_404(Project, id=project_id)

        if not project.user_has_access(request.user):
            messages.error(request, 'You do not have access to this project.')
            return redirect('image_list')

        files = request.FILES.getlist('image_files')
        if not files:
            messages.error(request, 'No file was selected.')
            return render(request, 'app/image_upload.html', {
                'projects': projects,
                'active_nav': 'upload',
            })

        uploaded = 0
        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                messages.warning(request, f'Invalid file type: {f.name}')
                continue
            if f.size > MAX_FILE_BYTES:
                messages.warning(request, f'File too large (max 20 MB): {f.name}')
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
            messages.success(
                request,
                f'Uploaded {uploaded} image(s) to project "{project.name}".'
            )
        return redirect('project_images', project_id=project.id)

    selected_project_id = request.GET.get('project')
    ctx = {
        'active_nav': 'upload',
        'projects': projects,
        'selected_project_id': int(selected_project_id) if selected_project_id else None,
    }
    return render(request, 'app/image_upload.html', ctx)


@login_required
@require_POST
def image_upload_ajax(request):
    """
    Upload a single image via fetch() (used by the folder-upload UI).

    Request body (multipart):
        project     – project pk
        image_file  – the file

    Response (JSON):
        { success: true,  name: "...", id: 123 }
        { success: false, error: "reason" }
    """
    project_id = request.POST.get('project', '').strip()
    if not project_id:
        return JsonResponse({'success': False, 'error': 'No project specified.'}, status=400)

    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Project not found.'}, status=404)

    if not project.user_has_access(request.user):
        return JsonResponse({'success': False, 'error': 'Access denied.'}, status=403)

    f = request.FILES.get('image_file')
    if not f:
        return JsonResponse({'success': False, 'error': 'No file received.'}, status=400)

    # Validate extension
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse(
            {'success': False, 'error': f'Unsupported file type "{ext}".'},
            status=400,
        )

    # Validate size
    if f.size > MAX_FILE_BYTES:
        return JsonResponse(
            {'success': False, 'error': f'File exceeds 20 MB limit ({f.size // (1024*1024)} MB).'},
            status=400,
        )

    try:
        image = Image.objects.create(
            project=project,
            uploaded_by=request.user,
            image_file=f,
            name=f.name,
            file_size=f.size,
        )
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    return JsonResponse({'success': True, 'name': image.name, 'id': image.pk})


@login_required
def image_delete(request, image_id):
    image = get_object_or_404(Image, id=image_id)
    project = image.project
    if not project.user_is_admin(request.user):
        messages.error(request, 'Only an administrator can delete images.')
    else:
        image.image_file.delete(save=False)
        image.delete()
        messages.success(request, f'Image "{image.name}" has been deleted.')
    return redirect('project_images', project_id=project.id)


def image_detail(request, pk):
    image = get_object_or_404(Image, pk=pk)
    return render(request, 'app/image_detail.html', {'image': image})


@login_required
def batch_tag(request):
    """Add or remove tags on multiple images at once."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    image_ids = request.POST.getlist('image_ids')
    tag_ids = request.POST.getlist('tag_ids')
    new_tag = request.POST.get('new_tag', '').strip()
    action = request.POST.get('action', 'add')  # 'add' | 'remove'

    accessible = Image.objects.filter(
        id__in=image_ids,
        project__in=_user_projects(request.user)
    )

    if new_tag:
        new_tag_color = request.POST.get('new_tag_color', '#6366f1').strip()
        tag_obj, _ = Tag.objects.get_or_create(
            name=new_tag,
            defaults={'created_by': request.user, 'color': new_tag_color}
        )
        tag_ids.append(str(tag_obj.id))

    tags = Tag.objects.filter(id__in=tag_ids)

    for image in accessible:
        if action == 'remove':
            image.tags.remove(*tags)
        else:
            image.tags.add(*tags)

    messages.success(
        request,
        f'{"Removed" if action == "remove" else "Added"} {len(tags)} tag(s) '
        f'for {accessible.count()} image(s).'
    )

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)
