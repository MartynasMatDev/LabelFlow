import os
import json
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.urls import reverse

from apps.projects.models import Project
from apps.projects.activity import log_activity
from apps.projects.workspace_utils import get_active_workspace
from .models import Image, Tag, BoundingBox, Polygon


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


def _user_projects(user, workspace=None):
    """Projects the user can see. When `workspace` is given, restrict
    to that workspace (honouring its access rules)."""
    if workspace is not None:
        if workspace.is_organization:
            return Project.objects.filter(workspace=workspace)
        return Project.objects.filter(workspace=workspace, created_by=user)
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
        # Top-level "Images" nav is scoped to the active workspace.
        workspace = get_active_workspace(request)
        images = Image.objects.filter(
            project__in=_user_projects(request.user, workspace=workspace)
        )

    status_filter = request.GET.get('status', '')
    if status_filter in ('pending', 'partial', 'done'):
        images = images.filter(status=status_filter)

    tag_filter = request.GET.get('tag', '')
    if tag_filter:
        images = images.filter(tags__id=tag_filter)

    q = request.GET.get('q', '').strip()
    if q:
        images = images.filter(name__icontains=q)

    start_date = request.GET.get('start_date', '').strip()
    end_date   = request.GET.get('end_date', '').strip()

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

    sort = request.GET.get('sort', '-uploaded_at')
    if sort in ('name', '-name', 'uploaded_at', '-uploaded_at', 'status'):
        images = images.order_by(sort)

    all_tags = Tag.objects.all()

    # Project-filter dropdown should list only projects the user can
    # see in the currently active workspace (unless a specific project
    # is already selected, in which case we still need its list).
    workspace_for_dropdown = None if project else get_active_workspace(request)
    ctx = {
        'active_nav': 'images',
        'project': project,
        'projects': _user_projects(request.user, workspace=workspace_for_dropdown),
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
    projects = _user_projects(request.user, workspace=get_active_workspace(request))

    if request.method == 'POST':
        project_id = request.POST.get('project')
        project    = get_object_or_404(Project, id=project_id)

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

            image = Image.objects.create(
                project=project,
                uploaded_by=request.user,
                image_file=f,
                name=f.name,
                file_size=f.size,
            )
            log_activity(project, request.user, 'image_uploaded', detail=image.name)
            uploaded += 1

        if uploaded:
            messages.success(request, f'Uploaded {uploaded} image(s) to project "{project.name}".')
        return redirect('project_images', project_id=project.id)

    selected_project_id  = request.GET.get('project')
    project_detail_base  = reverse('project_detail', args=[0])
    ctx = {
        'active_nav': 'upload',
        'projects': projects,
        'selected_project_id': int(selected_project_id) if selected_project_id else None,
        'project_detail_base': project_detail_base,
    }
    return render(request, 'app/image_upload.html', ctx)


@login_required
@require_POST
def image_upload_ajax(request):
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

    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({'success': False, 'error': f'Unsupported file type "{ext}".'}, status=400)

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
        log_activity(project, request.user, 'image_uploaded', detail=image.name)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    return JsonResponse({'success': True, 'name': image.name, 'id': image.pk})


@login_required
def image_delete(request, image_id):
    image   = get_object_or_404(Image, id=image_id)
    project = image.project
    if not project.user_is_admin(request.user):
        messages.error(request, 'Only an administrator can delete images.')
    else:
        name = image.name
        image.image_file.delete(save=False)
        image.delete()
        log_activity(project, request.user, 'image_deleted', detail=name)
        messages.success(request, f'Image "{name}" has been deleted.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('project_images', project_id=project.id)


@login_required
@require_POST
def batch_delete(request):
    image_ids  = request.POST.getlist('image_ids')
    accessible = Image.objects.filter(
        id__in=image_ids,
        project__in=_user_projects(request.user)
    )

    deleted_count = 0
    skipped_count = 0
    for image in accessible:
        if image.project.user_is_admin(request.user):
            name    = image.name
            project = image.project
            image.image_file.delete(save=False)
            image.delete()
            log_activity(project, request.user, 'image_deleted', detail=name)
            deleted_count += 1
        else:
            skipped_count += 1

    if deleted_count:
        messages.success(request, f'Deleted {deleted_count} image(s).')
    if skipped_count:
        messages.warning(request, f'{skipped_count} image(s) skipped — admin only.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)


def image_detail(request, pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this image.')
        return redirect('image_list')
    boxes    = [b.to_dict() for b in image.bounding_boxes.select_related('label').all()]
    polygons = [p.to_dict() for p in image.polygons.select_related('label').all()]
    return render(request, 'app/image_detail.html', {
        'image':         image,
        'active_nav':    'images',
        'project':       image.project,
        'boxes_json':    json.dumps(boxes),
        'polygons_json': json.dumps(polygons),
    })


# ─── ANNOTATION VIEWS ─────────────────────────────────────────────────────────

@login_required
def image_annotate(request, pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this image.')
        return redirect('image_list')

    boxes = [b.to_dict() for b in image.bounding_boxes.select_related('label').all()]
    all_tags = Tag.objects.all()
    polygons = [p.to_dict() for p in image.polygons.select_related('label').all()]

    ctx = {
        'active_nav': 'images',
        'project': image.project,
        'image': image,
        'boxes_json': json.dumps(boxes),
        'polygons_json': json.dumps(polygons),
        'all_tags': all_tags,
        'user_role': image.project.get_user_role(request.user) or 'admin',
    }
    return render(request, 'app/image_annotate.html', ctx)


@login_required
@require_POST
def annotation_save(request, pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        return JsonResponse({'error': 'Access denied.'}, status=403)

    try:
        data      = json.loads(request.body)
        incoming  = data.get('boxes', [])
        mark_done = data.get('mark_done', False)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    kept_ids = []
    saved    = []

    for b in incoming:
        box_id   = b.get('id')
        label_id = b.get('label_id')
        label    = Tag.objects.filter(pk=label_id).first() if label_id else None

        try:
            x      = float(b['x'])
            y      = float(b['y'])
            width  = float(b['width'])
            height = float(b['height'])
        except (KeyError, ValueError, TypeError):
            return JsonResponse({'error': 'Invalid box coordinates.'}, status=400)

        if not label and b.get('label_name'):
            label, _ = Tag.objects.get_or_create(
                name=b['label_name'],
                defaults={
                    'color':      b.get('label_color', '#6366f1'),
                    'created_by': request.user,
                }
            )

        if box_id:
            box = BoundingBox.objects.filter(pk=box_id, image=image).first()
            if box:
                box.label  = label
                box.x, box.y, box.width, box.height = x, y, width, height
                box.save()
                kept_ids.append(box.pk)
                saved.append(box.to_dict())
                continue

        box = BoundingBox.objects.create(
            image=image, label=label,
            x=x, y=y, width=width, height=height,
            created_by=request.user,
        )
        kept_ids.append(box.pk)
        saved.append(box.to_dict())

    image.bounding_boxes.exclude(pk__in=kept_ids).delete()

    # ── Handle polygons ──────────────────────────────────────
    incoming_polys = data.get('polygons', [])
    kept_poly_ids = []
    saved_polys = []

    for p in incoming_polys:
        poly_id = p.get('id')
        label_id = p.get('label_id')
        label = Tag.objects.filter(pk=label_id).first() if label_id else None
        points = p.get('points', [])

        if not isinstance(points, list) or len(points) < 3:
            continue

        if not label and p.get('label_name'):
            label, _ = Tag.objects.get_or_create(
                name=p['label_name'],
                defaults={
                    'color': p.get('label_color', '#6366f1'),
                    'created_by': request.user,
                }
            )

        if poly_id:
            poly = Polygon.objects.filter(pk=poly_id, image=image).first()
            if poly:
                poly.label = label
                poly.points = points
                poly.save()
                kept_poly_ids.append(poly.pk)
                saved_polys.append(poly.to_dict())
                continue

        poly = Polygon.objects.create(
            image=image, label=label, points=points, created_by=request.user
        )
        kept_poly_ids.append(poly.pk)
        saved_polys.append(poly.to_dict())

    image.polygons.exclude(pk__in=kept_poly_ids).delete()

    # Update status
    prev_status = image.status
    if mark_done:
        image.status = 'done'
    elif saved or saved_polys:
        image.status = 'partial'
    else:
        image.status = 'pending'
    image.save(update_fields=['status'])

    if mark_done and prev_status != 'done':
        log_activity(image.project, request.user, 'annotation_done',
                     detail=image.name, meta={'image_id': image.pk, 'box_count': len(saved) + len(saved_polys)})
    elif saved or saved_polys:
        log_activity(image.project, request.user, 'annotation_saved',
                     detail=image.name, meta={'image_id': image.pk, 'box_count': len(saved) + len(saved_polys)})

    return JsonResponse({'success': True, 'boxes': saved, 'polygons': saved_polys, 'status': image.status})


@login_required
@require_POST
def annotation_delete_box(request, pk, box_pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        return JsonResponse({'error': 'Access denied.'}, status=403)
    box = get_object_or_404(BoundingBox, pk=box_pk, image=image)
    box.delete()
    return JsonResponse({'success': True})


@login_required
def batch_tag(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    image_ids = request.POST.getlist('image_ids')
    tag_ids   = request.POST.getlist('tag_ids')
    new_tag   = request.POST.get('new_tag', '').strip()
    action    = request.POST.get('action', 'add')

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

    # Collect affected projects for logging
    projects_affected = {}
    for image in accessible:
        if action == 'remove':
            image.tags.remove(*tags)
        else:
            image.tags.add(*tags)
        projects_affected[image.project_id] = image.project

    tag_names = ', '.join(t.name for t in tags)
    for project in projects_affected.values():
        log_activity(
            project, request.user,
            'tag_removed' if action == 'remove' else 'tag_added',
            detail=tag_names,
        )

    messages.success(
        request,
        f'{"Removed" if action == "remove" else "Added"} {len(tags)} tag(s) '
        f'for {accessible.count()} image(s).'
    )

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)

@login_required
@require_POST
def polygon_delete(request, pk, poly_pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        return JsonResponse({'error': 'Access denied.'}, status=403)
    poly = get_object_or_404(Polygon, pk=poly_pk, image=image)
    poly.delete()
    return JsonResponse({'success': True})