import io
import os
import json
import zipfile
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.urls import reverse

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image as PILImage

from apps.projects.models import Project
from apps.projects.activity import log_activity
from apps.projects.workspace_utils import get_active_workspace
from .models import Image, Tag, BoundingBox, Polygon, SegmentationMask
from .models import Image, BoundingBox, ImageComment

import requests
from django.core.files.base import ContentFile
import io, urllib.request, urllib.parse, urllib.error, imghdr
from django.core.files.base import ContentFile
from apps.projects.models import Project as ProjectModel

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB

TARGET_SIZE   = 1024
TARGET_FORMAT = 'JPEG'
TARGET_EXT    = '.jpg'
JPEG_QUALITY  = 92

def _normalise_upload(django_file, original_name):
    django_file.seek(0)
    img = PILImage.open(django_file)
    img.load()

    if img.mode in ('RGBA', 'LA'):
        bg = PILImage.new('RGB', img.size, (0, 0, 0))
        bg.paste(img.convert('RGB'), mask=img.split()[-1])
        img = bg
    elif img.mode == 'P':
        img = img.convert('RGBA')
        bg = PILImage.new('RGB', img.size, (0, 0, 0))
        bg.paste(img.convert('RGB'), mask=img.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    w, h = img.size
    if w < h:
        img = img.resize((TARGET_SIZE, int(h * TARGET_SIZE / w)), PILImage.LANCZOS)
    else:
        img = img.resize((int(w * TARGET_SIZE / h), TARGET_SIZE), PILImage.LANCZOS)

    img = _smart_crop(img, TARGET_SIZE)

    buf = io.BytesIO()
    img.save(buf, format=TARGET_FORMAT, quality=JPEG_QUALITY)
    buf_size = buf.tell()
    buf.seek(0)

    return InMemoryUploadedFile(
        file=buf, field_name='image_file',
        name=os.path.splitext(original_name)[0] + TARGET_EXT,
        content_type='image/jpeg', size=buf_size, charset=None,
    )

def _download_image_from_url(url):
    try:
        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to download: {e}")

    content_type = response.headers.get('Content-Type', '')
    if not content_type.startswith('image/'):
        raise ValueError("URL does not point to an image")

    content = response.content
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("File too large")

    name = url.split('/')[-1].split('?')[0] or 'image.jpg'

    return ContentFile(content, name=name)

def _smart_crop(img, size):
    w, h = img.size
    if w == size and h == size:
        return img

    if w > h:
        max_offset = w - size
        def make_box(o): return (o, 0, o + size, size)
    else:
        max_offset = h - size
        def make_box(o): return (0, o, size, o + size)

    steps = min(max_offset + 1, 16)
    offsets = [int(max_offset * i / (steps - 1)) for i in range(steps)] if steps > 1 else [max_offset // 2]

    best_offset  = offsets[len(offsets) // 2]
    best_entropy = -1.0
    grey = img.convert('L')

    for offset in offsets:
        e = _entropy(grey.crop(make_box(offset)))
        if e > best_entropy:
            best_entropy = e
            best_offset  = offset

    return img.crop(make_box(best_offset))


def _entropy(grey_tile):
    import math
    hist  = grey_tile.histogram()
    total = sum(hist)
    if total == 0:
        return 0.0
    return -sum((p / total) * math.log2(p / total) for p in hist if p > 0)

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

    annotation_type_filter = request.GET.get('annotation_type', '')
    if annotation_type_filter:
        images = images.filter(project__annotation_type=annotation_type_filter)

    q = request.GET.get('q', '').strip()
    if q:
        images = images.filter(name__icontains=q)

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

    sort = request.GET.get('sort', '-uploaded_at')
    if sort in ('name', '-name', 'uploaded_at', '-uploaded_at', 'status'):
        images = images.order_by(sort)

    all_tags = Tag.objects.all()

    annotation_types = ProjectModel.ANNOTATION_TYPE_CHOICES

    workspace_for_dropdown = None if project else get_active_workspace(request)
    ctx = {
        'active_nav': 'images',
        'project': project,
        'projects': _user_projects(request.user, workspace=workspace_for_dropdown),
        'images': images,
        'image_count': images.count(),
        'status_filter': status_filter,
        'tag_filter': tag_filter,
        'annotation_type_filter': annotation_type_filter,
        'annotation_types': annotation_types,
        'all_tags': all_tags,
        'q': q,
        'sort': sort,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'app/image_list.html', ctx)


@login_required
def image_upload(request):
    files = request.FILES.getlist('image_files')
    urls_raw = request.POST.get('image_urls', '').strip()
    url_list = [u.strip() for u in urls_raw.splitlines() if u.strip()]
    projects = _user_projects(request.user, workspace=get_active_workspace(request))

    if request.method == 'POST':
        project_id = request.POST.get('project')
        project    = get_object_or_404(Project, id=project_id)

        if not project.user_has_access(request.user):
            messages.error(request, 'You do not have access to this project.')
            return redirect('image_list')

        files = request.FILES.getlist('image_files')
        if not files and not url_list:
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

            try:
                normalised = _normalise_upload(f, f.name)
            except Exception as exc:
                messages.warning(request, f'Could not process "{f.name}": {exc}')
                continue

            image = Image.objects.create(
                project=project,
                uploaded_by=request.user,
                image_file=normalised,
                name=normalised.name,
                file_size=normalised.size,
            )

            log_activity(project, request.user, 'image_uploaded', detail=image.name)
            uploaded += 1

        for url in url_list:
            try:
                downloaded = _download_image_from_url(url)

                if downloaded.size > MAX_FILE_BYTES:
                    messages.warning(request, f'File too large (from URL): {url}')
                    continue

                ext = os.path.splitext(downloaded.name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    downloaded.name += '.jpg'

                normalised = _normalise_upload(downloaded, downloaded.name)

            except Exception as exc:
                messages.warning(request, f'Failed URL "{url}": {exc}')
                continue

            image = Image.objects.create(
                project=project,
                uploaded_by=request.user,
                image_file=normalised,
                name=normalised.name,
                file_size=normalised.size,
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
    url = request.POST.get('image_url', '').strip()
    urls_raw = request.POST.get('image_urls', '').strip()
    url_list = [u.strip() for u in urls_raw.splitlines() if u.strip()]

    image_urls_raw = request.POST.get('image_urls', '').strip()
    if image_urls_raw:
        project_id = request.POST.get('project')
        project = get_object_or_404(Project, pk=project_id)
        if not project.user_has_access(request.user):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        urls = [u.strip() for u in image_urls_raw.splitlines() if u.strip()]
        imported = []
        errors = []

        for raw_url in urls:
            try:
                parsed = urllib.parse.urlparse(raw_url)
                if parsed.scheme not in ('http', 'https'):
                    errors.append({'url': raw_url, 'error': 'Only http/https URLs are supported.'})
                    continue

                req = urllib.request.Request(raw_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content_type = resp.headers.get_content_type()
                    if not content_type.startswith('image/'):
                        errors.append({'url': raw_url, 'error': f'Not an image ({content_type}).'})
                        continue
                    data = resp.read(20 * 1024 * 1024)

                ext_map = {'image/jpeg': 'jpg', 'image/png': 'png',
                           'image/webp': 'webp', 'image/gif': 'gif', 'image/bmp': 'bmp'}
                ext = ext_map.get(content_type, imghdr.what(None, h=data) or 'jpg')

                filename = os.path.basename(urllib.parse.urlparse(raw_url).path) or f'import.{ext}'
                if not any(filename.lower().endswith(e) for e in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')):
                    filename = f'{filename}.{ext}'

                img_obj = Image(project=project, uploaded_by=request.user,
                                file_size=len(data), name=filename)
                img_obj.image_file.save(filename, ContentFile(data), save=True)
                imported.append({'name': filename, 'id': img_obj.pk})

            except urllib.error.URLError as e:
                errors.append({'url': raw_url, 'error': str(e.reason)})
            except Exception as e:
                errors.append({'url': raw_url, 'error': str(e)})

        log_activity(project, request.user, 'image_uploaded',
                         detail=f'{len(imported)} image(s) imported from URL')

        return JsonResponse({'success': True, 'imported': imported, 'errors': errors})

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
    if not f and not url and not url_list:
        return JsonResponse({'success': False, 'error': 'No file or URL provided.'}, status=400)

    if url_list:
        uploaded = 0

        for url in url_list:
            try:
                downloaded = _download_image_from_url(url)
                normalised = _normalise_upload(downloaded, downloaded.name)

                image = Image.objects.create(
                    project=project,
                    uploaded_by=request.user,
                    image_file=normalised,
                    name=normalised.name,
                    file_size=normalised.size,
                )

                log_activity(project, request.user, 'image_uploaded', detail=image.name)
                uploaded += 1

            except Exception as exc:
                continue

        return JsonResponse({'success': True, 'uploaded': uploaded})

    if url:
        try:
            downloaded = _download_image_from_url(url)

            if downloaded.size > MAX_FILE_BYTES:
                return JsonResponse({'success': False, 'error': 'File too large.'}, status=400)

            normalised = _normalise_upload(downloaded, downloaded.name)

            image = Image.objects.create(
                project=project,
                uploaded_by=request.user,
                image_file=normalised,
                name=normalised.name,
                file_size=normalised.size,
            )

            log_activity(project, request.user, 'image_uploaded', detail=image.name)

            return JsonResponse({'success': True, 'name': image.name, 'id': image.pk})

        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({'success': False, 'error': f'Unsupported file type "{ext}".'}, status=400)

    if f.size > MAX_FILE_BYTES:
        return JsonResponse(
            {'success': False, 'error': f'File exceeds 20 MB limit ({f.size // (1024*1024)} MB).'},
            status=400,
        )

    try:
        normalised = _normalise_upload(f, f.name)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': f'Image processing failed: {exc}'}, status=500)

    try:
        image = Image.objects.create(
            project=project,
            uploaded_by=request.user,
            image_file=normalised,
            name=normalised.name,
            file_size=normalised.size,
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
        _cleanup_orphan_tags()
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
            _cleanup_orphan_tags()
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

    comments = image.comments.select_related('author').all()
    for c in comments:
        c.can_delete = (c.author == request.user or image.project.user_is_admin(request.user))

    return render(request, 'app/image_detail.html', {
        'image':         image,
        'active_nav':    'images',
        'project':       image.project,
        'boxes_json':    json.dumps(boxes),
        'polygons_json': json.dumps(polygons),
        'comments':      comments,
    })


# ─── ANNOTATION VIEWS ─────────────────────────────────────────────────────────

@login_required
def image_annotate(request, pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this image.')
        return redirect('image_list')

    boxes    = [b.to_dict() for b in image.bounding_boxes.select_related('label').all()]
    polygons = [p.to_dict() for p in image.polygons.select_related('label').all()]
    seg_masks = [m.to_dict() for m in image.seg_masks.select_related('label').all()]
    all_tags = Tag.objects.all()

    ctx = {
        'active_nav':    'images',
        'project':       image.project,
        'image':         image,
        'boxes_json':    json.dumps(boxes),
        'polygons_json': json.dumps(polygons),
        'seg_masks_json': json.dumps(seg_masks),
        'all_tags':      all_tags,
        'user_role':     image.project.get_user_role(request.user) or 'admin',
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
def segmentation_save(request, pk):
    image = get_object_or_404(Image, pk=pk)
    if not image.project.user_has_access(request.user):
        return JsonResponse({'error': 'Access denied.'}, status=403)

    try:
        data      = json.loads(request.body)
        incoming  = data.get('masks', [])
        mark_done = data.get('mark_done', False)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    kept_ids = []
    saved    = []

    for m in incoming:
        mask_id   = m.get('id')
        label_id  = m.get('label_id')
        mask_data = m.get('mask_data', '')

        if not mask_data:
            continue

        label = Tag.objects.filter(pk=label_id).first() if label_id else None
        if not label and m.get('label_name'):
            label, _ = Tag.objects.get_or_create(
                name=m['label_name'],
                defaults={'color': m.get('label_color', '#6366f1'), 'created_by': request.user},
            )

        if mask_id:
            mask = SegmentationMask.objects.filter(pk=mask_id, image=image).first()
            if mask:
                mask.label     = label
                mask.mask_data = mask_data
                mask.save()
                kept_ids.append(mask.pk)
                saved.append(mask.to_meta())
                continue

        mask = SegmentationMask.objects.create(
            image=image, label=label, mask_data=mask_data, created_by=request.user,
        )
        kept_ids.append(mask.pk)
        saved.append(mask.to_meta())

    image.seg_masks.exclude(pk__in=kept_ids).delete()

    prev_status = image.status
    if mark_done:
        image.status = 'done'
    elif saved:
        image.status = 'partial'
    else:
        image.status = 'pending'
    image.save(update_fields=['status'])

    if mark_done and prev_status != 'done':
        log_activity(image.project, request.user, 'annotation_done',
                     detail=image.name, meta={'image_id': image.pk, 'mask_count': len(saved)})
    elif saved:
        log_activity(image.project, request.user, 'annotation_saved',
                     detail=image.name, meta={'image_id': image.pk, 'mask_count': len(saved)})

    return JsonResponse({'success': True, 'masks': saved, 'status': image.status})


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


# ─── CLEANUP ORPHAN TAGS ──────────────────────────────────────────────────────

def _cleanup_orphan_tags():
    """Delete tags that are no longer used by any image, bounding box, or polygon."""
    Tag.objects.filter(
        images__isnull=True,
        bounding_boxes__isnull=True,
        polygons__isnull=True,
    ).delete()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _parse_export_image_ids(request):
    """
    Return a list of integer image IDs from POST or GET, or None if none supplied.
    Supports both POST (form submission from export modal) and GET (direct URL).
    """
    raw = request.POST.getlist('image_ids') or request.GET.getlist('image_ids')
    ids = [int(i) for i in raw if i.isdigit()]
    return ids if ids else None


# ─── YOLO EXPORT ──────────────────────────────────────────────────────────────

def build_yolo_zip(project, status_filter='', image_ids=None):
    """
    Build a YOLO-format zip for a project.
    If image_ids is given, only those images are included (ignores status_filter).
    Returns (bytes, filename, image_count).
    """
    images_qs = Image.objects.filter(project=project).prefetch_related(
        'bounding_boxes__label', 'polygons__label'
    )
    if image_ids is not None:
        images_qs = images_qs.filter(pk__in=image_ids)
    elif status_filter in ('pending', 'partial', 'done'):
        images_qs = images_qs.filter(status=status_filter)

    label_set = {}
    for image in images_qs:
        for box in image.bounding_boxes.all():
            if box.label and box.label.id not in label_set:
                label_set[box.label.id] = box.label.name
        for poly in image.polygons.all():
            if poly.label and poly.label.id not in label_set:
                label_set[poly.label.id] = poly.label.name
    label_index = {lid: idx for idx, lid in enumerate(label_set)}
    class_names = [label_set[lid] for lid in label_set]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            stem = os.path.splitext(image.name)[0]
            if image.image_file and os.path.exists(image.image_file.path):
                ext = os.path.splitext(image.image_file.name)[1]
                zf.write(image.image_file.path, f'images/{stem}{ext}')

            lines = []
            for box in image.bounding_boxes.all():
                if box.label is None:
                    continue
                cls = label_index[box.label.id]
                x_c = (box.x + box.width / 2) / 100
                y_c = (box.y + box.height / 2) / 100
                w = box.width / 100
                h = box.height / 100
                lines.append(f'{cls} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}')
            for poly in image.polygons.all():
                if poly.label is None:
                    continue
                cls = label_index[poly.label.id]
                coords = ' '.join(
                    f'{p["x"] / 100:.6f} {p["y"] / 100:.6f}'
                    for p in poly.points
                )
                lines.append(f'{cls} {coords}')

            zf.writestr(f'labels/{stem}.txt', '\n'.join(lines))

        zf.writestr('classes.txt', '\n'.join(class_names))
        yaml_lines = [
            'path: .',
            'train: images',
            'val: images',
            '',
            f'nc: {len(class_names)}',
            f'names: {json.dumps(class_names)}',
        ]
        zf.writestr('data.yaml', '\n'.join(yaml_lines))

    buf.seek(0)
    slug = project.name.lower().replace(' ', '_')
    return buf.read(), f'{slug}_yolo.zip', images_qs.count()


@login_required
def export_yolo(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')

    image_ids = _parse_export_image_ids(request)
    status_filter = request.GET.get('status', '')
    data, filename, count = build_yolo_zip(project, status_filter, image_ids=image_ids)
    log_activity(project, request.user, 'export_yolo', detail=f'{count} images')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def public_export_yolo(request, share_token):
    """Public, no-auth download of a project's YOLO dataset by share token."""
    project = get_object_or_404(Project, share_token=share_token, is_public=True, is_archived=False)
    data, filename, _ = build_yolo_zip(project, status_filter='done')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── CSV EXPORT ───────────────────────────────────────────────────────────────

def build_csv_zip(project, status_filter='', image_ids=None):
    """
    Build a CSV-format zip for a project.
    If image_ids is given, only those images are included (ignores status_filter).
    Returns (bytes, filename, image_count).
    """
    import csv

    images_qs = Image.objects.filter(project=project).prefetch_related(
        'bounding_boxes__label', 'polygons__label', 'tags'
    )
    if image_ids is not None:
        images_qs = images_qs.filter(pk__in=image_ids)
    elif status_filter in ('pending', 'partial', 'done'):
        images_qs = images_qs.filter(status=status_filter)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            if image.image_file and os.path.exists(image.image_file.path):
                zf.write(image.image_file.path, f'images/{image.name}')

        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow([
            'image_id', 'image_name', 'image_status',
            'annotation_type', 'annotation_id',
            'label', 'label_color',
            'x', 'y', 'width', 'height',
            'points', 'tags',
        ])

        for image in images_qs:
            tags_str = '|'.join(t.name for t in image.tags.all())

            for box in image.bounding_boxes.all():
                writer.writerow([
                    image.pk, image.name, image.status,
                    'bbox', box.pk,
                    box.label.name if box.label else '',
                    box.label.color if box.label else '',
                    round(box.x, 4), round(box.y, 4),
                    round(box.width, 4), round(box.height, 4),
                    '', tags_str,
                ])

            for poly in image.polygons.all():
                points_str = ';'.join(f"{p['x']:.4f},{p['y']:.4f}" for p in poly.points)
                writer.writerow([
                    image.pk, image.name, image.status,
                    'polygon', poly.pk,
                    poly.label.name if poly.label else '',
                    poly.label.color if poly.label else '',
                    '', '', '', '',
                    points_str, tags_str,
                ])

            if not image.bounding_boxes.exists() and not image.polygons.exists():
                writer.writerow([
                    image.pk, image.name, image.status,
                    '', '', '', '', '', '', '', '', '', tags_str,
                ])

        zf.writestr('annotations/annotations.csv', csv_buf.getvalue())

    buf.seek(0)
    slug = project.name.lower().replace(' ', '_')
    return buf.read(), f'{slug}_csv.zip', images_qs.count()


@login_required
def export_csv(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')

    image_ids = _parse_export_image_ids(request)
    status_filter = request.GET.get('status', '')
    data, filename, count = build_csv_zip(project, status_filter, image_ids=image_ids)
    log_activity(project, request.user, 'export_csv', detail=f'{count} images')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def public_export_csv(request, share_token):
    project = get_object_or_404(Project, share_token=share_token, is_public=True, is_archived=False)
    data, filename, _ = build_csv_zip(project, status_filter='done')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── COCO EXPORT ──────────────────────────────────────────────────────────────

def build_coco_zip(project, status_filter='', image_ids=None):
    """
    Build a COCO-format zip for a project.
    If image_ids is given, only those images are included (ignores status_filter).
    Returns (bytes, filename, image_count).
    """
    images_qs = Image.objects.filter(project=project).prefetch_related(
        'bounding_boxes__label', 'polygons__label'
    )
    if image_ids is not None:
        images_qs = images_qs.filter(pk__in=image_ids)
    elif status_filter in ('pending', 'partial', 'done'):
        images_qs = images_qs.filter(status=status_filter)

    label_set = {}
    for image in images_qs:
        for box in image.bounding_boxes.all():
            if box.label and box.label.id not in label_set:
                label_set[box.label.id] = box.label.name
        for poly in image.polygons.all():
            if poly.label and poly.label.id not in label_set:
                label_set[poly.label.id] = poly.label.name

    cat_id_map = {lid: idx + 1 for idx, lid in enumerate(label_set)}
    categories = [
        {'id': cat_id_map[lid], 'name': name, 'supercategory': 'object'}
        for lid, name in label_set.items()
    ]

    coco_images = []
    coco_annotations = []
    ann_id = 1

    for image in images_qs:
        img_w, img_h = 1024, 1024
        try:
            if image.image_file and os.path.exists(image.image_file.path):
                with PILImage.open(image.image_file.path) as pil:
                    img_w, img_h = pil.size
        except Exception:
            pass

        coco_images.append({
            'id': image.pk,
            'file_name': f'images/{image.name}',
            'width': img_w,
            'height': img_h,
        })

        for box in image.bounding_boxes.all():
            if box.label is None:
                continue
            abs_x = box.x / 100 * img_w
            abs_y = box.y / 100 * img_h
            abs_w = box.width / 100 * img_w
            abs_h = box.height / 100 * img_h
            coco_annotations.append({
                'id': ann_id,
                'image_id': image.pk,
                'category_id': cat_id_map[box.label.id],
                'bbox': [round(abs_x, 2), round(abs_y, 2), round(abs_w, 2), round(abs_h, 2)],
                'area': round(abs_w * abs_h, 2),
                'segmentation': [],
                'iscrowd': 0,
            })
            ann_id += 1

        for poly in image.polygons.all():
            if poly.label is None:
                continue
            seg = []
            for pt in poly.points:
                seg.append(round(pt['x'] / 100 * img_w, 2))
                seg.append(round(pt['y'] / 100 * img_h, 2))
            xs = seg[0::2]
            ys = seg[1::2]
            bbox_x, bbox_y = min(xs), min(ys)
            bbox_w, bbox_h = max(xs) - bbox_x, max(ys) - bbox_y
            coco_annotations.append({
                'id': ann_id,
                'image_id': image.pk,
                'category_id': cat_id_map[poly.label.id],
                'bbox': [round(bbox_x, 2), round(bbox_y, 2), round(bbox_w, 2), round(bbox_h, 2)],
                'area': round(bbox_w * bbox_h, 2),
                'segmentation': [seg],
                'iscrowd': 0,
            })
            ann_id += 1

    coco_dict = {
        'info': {
            'description': project.name,
            'version': '1.0',
            'year': datetime.now().year,
            'date_created': datetime.now().strftime('%Y/%m/%d'),
        },
        'licenses': [],
        'categories': categories,
        'images': coco_images,
        'annotations': coco_annotations,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            if image.image_file and os.path.exists(image.image_file.path):
                zf.write(image.image_file.path, f'images/{image.name}')

        zf.writestr('annotations/instances_default.json', json.dumps(coco_dict, ensure_ascii=False, indent=2))

    buf.seek(0)
    slug = project.name.lower().replace(' ', '_')
    return buf.read(), f'{slug}_coco.zip', images_qs.count()


@login_required
def export_coco(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')

    image_ids = _parse_export_image_ids(request)
    status_filter = request.GET.get('status', '')
    data, filename, count = build_coco_zip(project, status_filter, image_ids=image_ids)
    log_activity(project, request.user, 'export_coco', detail=f'{count} images')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def public_export_coco(request, share_token):
    project = get_object_or_404(Project, share_token=share_token, is_public=True, is_archived=False)
    data, filename, _ = build_coco_zip(project, status_filter='done')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── JSON EXPORT ──────────────────────────────────────────────────────────────

def build_json_zip(project, status_filter='', image_ids=None):
    """
    Build a generic JSON-format zip for a project.
    If image_ids is given, only those images are included (ignores status_filter).
    Returns (bytes, filename, image_count).
    """
    images_qs = Image.objects.filter(project=project).prefetch_related(
        'bounding_boxes__label', 'polygons__label', 'tags'
    )
    if image_ids is not None:
        images_qs = images_qs.filter(pk__in=image_ids)
    elif status_filter in ('pending', 'partial', 'done'):
        images_qs = images_qs.filter(status=status_filter)

    output = {
        'project': {
            'id': project.pk,
            'name': project.name,
            'annotation_type': project.annotation_type,
            'exported_at': datetime.now().isoformat(),
        },
        'images': [],
    }

    for image in images_qs:
        img_entry = {
            'id': image.pk,
            'name': image.name,
            'status': image.status,
            'uploaded_at': image.uploaded_at.isoformat() if hasattr(image, 'uploaded_at') else None,
            'tags': [t.name for t in image.tags.all()],
            'bounding_boxes': [],
            'polygons': [],
        }

        for box in image.bounding_boxes.all():
            img_entry['bounding_boxes'].append({
                'id': box.pk,
                'label': box.label.name if box.label else None,
                'label_color': box.label.color if box.label else None,
                'x': round(box.x, 4),
                'y': round(box.y, 4),
                'width': round(box.width, 4),
                'height': round(box.height, 4),
            })

        for poly in image.polygons.all():
            img_entry['polygons'].append({
                'id': poly.pk,
                'label': poly.label.name if poly.label else None,
                'label_color': poly.label.color if poly.label else None,
                'points': [{'x': round(p['x'], 4), 'y': round(p['y'], 4)} for p in poly.points],
            })

        output['images'].append(img_entry)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            if image.image_file and os.path.exists(image.image_file.path):
                zf.write(image.image_file.path, f'images/{image.name}')

        zf.writestr('annotations/annotations.json', json.dumps(output, ensure_ascii=False, indent=2))

    buf.seek(0)
    slug = project.name.lower().replace(' ', '_')
    return buf.read(), f'{slug}_json.zip', images_qs.count()


@login_required
def export_json(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'You do not have access to this project.')
        return redirect('project_list')

    image_ids = _parse_export_image_ids(request)
    status_filter = request.GET.get('status', '')
    data, filename, count = build_json_zip(project, status_filter, image_ids=image_ids)
    log_activity(project, request.user, 'export_json', detail=f'{count} images')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def public_export_json(request, share_token):
    project = get_object_or_404(Project, share_token=share_token, is_public=True, is_archived=False)
    data, filename, _ = build_json_zip(project, status_filter='done')
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def batch_export(request):
    image_ids = request.POST.getlist('image_ids')
    fmt = request.POST.get('format', 'yolo')

    images_qs = Image.objects.filter(
        id__in=image_ids,
        project__in=_user_projects(request.user)
    ).prefetch_related('bounding_boxes__label', 'polygons__label', 'tags')

    if not images_qs.exists():
        messages.error(request, 'No accessible images selected.')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
        return redirect(next_url)

    if fmt == 'yolo':
        data, filename = _build_yolo_zip_from_qs(images_qs)
    elif fmt == 'csv':
        data, filename = _build_csv_zip_from_qs(images_qs)
    elif fmt == 'coco':
        data, filename = _build_coco_zip_from_qs(images_qs)
    elif fmt == 'json':
        data, filename = _build_json_zip_from_qs(images_qs)
    else:
        messages.error(request, 'Unknown export format.')
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '/')
        return redirect(next_url)

    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _build_yolo_zip_from_qs(images_qs):
    label_set = {}
    for image in images_qs:
        for box in image.bounding_boxes.all():
            if box.label and box.label.id not in label_set:
                label_set[box.label.id] = box.label.name
        for poly in image.polygons.all():
            if poly.label and poly.label.id not in label_set:
                label_set[poly.label.id] = poly.label.name
    label_index = {lid: idx for idx, lid in enumerate(label_set)}
    class_names = [label_set[lid] for lid in label_set]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            stem = os.path.splitext(image.name)[0]
            if image.image_file and os.path.exists(image.image_file.path):
                ext = os.path.splitext(image.image_file.name)[1]
                zf.write(image.image_file.path, f'images/{stem}{ext}')
            lines = []
            for box in image.bounding_boxes.all():
                if box.label is None:
                    continue
                cls = label_index[box.label.id]
                x_c = (box.x + box.width / 2) / 100
                y_c = (box.y + box.height / 2) / 100
                lines.append(f'{cls} {x_c:.6f} {y_c:.6f} {box.width/100:.6f} {box.height/100:.6f}')
            for poly in image.polygons.all():
                if poly.label is None:
                    continue
                cls = label_index[poly.label.id]
                coords = ' '.join(f'{p["x"]/100:.6f} {p["y"]/100:.6f}' for p in poly.points)
                lines.append(f'{cls} {coords}')
            zf.writestr(f'labels/{stem}.txt', '\n'.join(lines))
        zf.writestr('classes.txt', '\n'.join(class_names))
        zf.writestr('data.yaml', '\n'.join([
            'path: .', 'train: images', 'val: images', '',
            f'nc: {len(class_names)}', f'names: {json.dumps(class_names)}',
        ]))
    buf.seek(0)
    return buf.read(), 'selected_images_yolo.zip'


def _build_csv_zip_from_qs(images_qs):
    import csv as csv_mod
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            if image.image_file and os.path.exists(image.image_file.path):
                zf.write(image.image_file.path, f'images/{image.name}')
        csv_buf = io.StringIO()
        writer = csv_mod.writer(csv_buf)
        writer.writerow(['image_id', 'image_name', 'image_status', 'annotation_type',
                         'annotation_id', 'label', 'label_color', 'x', 'y', 'width', 'height', 'points', 'tags'])
        for image in images_qs:
            tags_str = '|'.join(t.name for t in image.tags.all())
            for box in image.bounding_boxes.all():
                writer.writerow([image.pk, image.name, image.status, 'bbox', box.pk,
                                 box.label.name if box.label else '', box.label.color if box.label else '',
                                 round(box.x, 4), round(box.y, 4), round(box.width, 4), round(box.height, 4), '', tags_str])
            for poly in image.polygons.all():
                points_str = ';'.join(f"{p['x']:.4f},{p['y']:.4f}" for p in poly.points)
                writer.writerow([image.pk, image.name, image.status, 'polygon', poly.pk,
                                 poly.label.name if poly.label else '', poly.label.color if poly.label else '',
                                 '', '', '', '', points_str, tags_str])
            if not image.bounding_boxes.exists() and not image.polygons.exists():
                writer.writerow([image.pk, image.name, image.status, '', '', '', '', '', '', '', '', '', tags_str])
        zf.writestr('annotations/annotations.csv', csv_buf.getvalue())
    buf.seek(0)
    return buf.read(), 'selected_images_csv.zip'


def _build_coco_zip_from_qs(images_qs):
    label_set = {}
    for image in images_qs:
        for box in image.bounding_boxes.all():
            if box.label and box.label.id not in label_set:
                label_set[box.label.id] = box.label.name
        for poly in image.polygons.all():
            if poly.label and poly.label.id not in label_set:
                label_set[poly.label.id] = poly.label.name
    cat_id_map = {lid: idx + 1 for idx, lid in enumerate(label_set)}
    categories = [{'id': cat_id_map[lid], 'name': name, 'supercategory': 'object'} for lid, name in label_set.items()]
    coco_images, coco_annotations, ann_id = [], [], 1
    for image in images_qs:
        img_w, img_h = 1024, 1024
        try:
            if image.image_file and os.path.exists(image.image_file.path):
                with PILImage.open(image.image_file.path) as pil:
                    img_w, img_h = pil.size
        except Exception:
            pass
        coco_images.append({'id': image.pk, 'file_name': f'images/{image.name}', 'width': img_w, 'height': img_h})
        for box in image.bounding_boxes.all():
            if not box.label:
                continue
            abs_x, abs_y = box.x / 100 * img_w, box.y / 100 * img_h
            abs_w, abs_h = box.width / 100 * img_w, box.height / 100 * img_h
            coco_annotations.append({'id': ann_id, 'image_id': image.pk, 'category_id': cat_id_map[box.label.id],
                                     'bbox': [round(abs_x, 2), round(abs_y, 2), round(abs_w, 2), round(abs_h, 2)],
                                     'area': round(abs_w * abs_h, 2), 'segmentation': [], 'iscrowd': 0})
            ann_id += 1
        for poly in image.polygons.all():
            if not poly.label:
                continue
            seg = [coord for pt in poly.points for coord in (round(pt['x'] / 100 * img_w, 2), round(pt['y'] / 100 * img_h, 2))]
            xs, ys = seg[0::2], seg[1::2]
            bbox_x, bbox_y = min(xs), min(ys)
            bbox_w, bbox_h = max(xs) - bbox_x, max(ys) - bbox_y
            coco_annotations.append({'id': ann_id, 'image_id': image.pk, 'category_id': cat_id_map[poly.label.id],
                                     'bbox': [round(bbox_x, 2), round(bbox_y, 2), round(bbox_w, 2), round(bbox_h, 2)],
                                     'area': round(bbox_w * bbox_h, 2), 'segmentation': [seg], 'iscrowd': 0})
            ann_id += 1
    coco_dict = {
        'info': {'description': 'Selected images', 'version': '1.0',
                 'year': datetime.now().year, 'date_created': datetime.now().strftime('%Y/%m/%d')},
        'licenses': [], 'categories': categories, 'images': coco_images, 'annotations': coco_annotations,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            if image.image_file and os.path.exists(image.image_file.path):
                zf.write(image.image_file.path, f'images/{image.name}')
        zf.writestr('annotations/instances_default.json', json.dumps(coco_dict, ensure_ascii=False, indent=2))
    buf.seek(0)
    return buf.read(), 'selected_images_coco.zip'


def _build_json_zip_from_qs(images_qs):
    output = {'exported_at': datetime.now().isoformat(), 'images': []}
    for image in images_qs:
        img_entry = {
            'id': image.pk, 'name': image.name, 'status': image.status,
            'uploaded_at': image.uploaded_at.isoformat() if hasattr(image, 'uploaded_at') else None,
            'tags': [t.name for t in image.tags.all()],
            'bounding_boxes': [], 'polygons': [],
        }
        for box in image.bounding_boxes.all():
            img_entry['bounding_boxes'].append({'id': box.pk, 'label': box.label.name if box.label else None,
                                                'label_color': box.label.color if box.label else None,
                                                'x': round(box.x, 4), 'y': round(box.y, 4),
                                                'width': round(box.width, 4), 'height': round(box.height, 4)})
        for poly in image.polygons.all():
            img_entry['polygons'].append({'id': poly.pk, 'label': poly.label.name if poly.label else None,
                                          'label_color': poly.label.color if poly.label else None,
                                          'points': [{'x': round(p['x'], 4), 'y': round(p['y'], 4)} for p in poly.points]})
        output['images'].append(img_entry)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for image in images_qs:
            if image.image_file and os.path.exists(image.image_file.path):
                zf.write(image.image_file.path, f'images/{image.name}')
        zf.writestr('annotations/annotations.json', json.dumps(output, ensure_ascii=False, indent=2))
    buf.seek(0)
    return buf.read(), 'selected_images_json.zip'


@login_required
def dataset_import(request):
    projects = _user_projects(request.user, workspace=get_active_workspace(request))

    if request.method != 'POST':
        selected_project_id = request.GET.get('project')
        return render(request, 'app/dataset_import.html', {
            'active_nav': 'upload',
            'projects': projects,
            'selected_project_id': int(selected_project_id) if selected_project_id else None,
        })

    project_id = request.POST.get('project')
    fmt = request.POST.get('format', 'yolo')
    zip_file = request.FILES.get('zip_file')

    if not project_id or not zip_file:
        messages.error(request, 'Please select a project and a ZIP file.')
        return redirect(request.path)

    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        messages.error(request, 'Access denied.')
        return redirect('project_list')

    if not zip_file.name.endswith('.zip'):
        messages.error(request, 'File must be a .zip archive.')
        return redirect(request.path)

    try:
        if fmt == 'yolo':
            imported, skipped = _import_yolo(zip_file, project, request.user)
        elif fmt == 'coco':
            imported, skipped = _import_coco(zip_file, project, request.user)
        elif fmt == 'csv':
            imported, skipped = _import_csv(zip_file, project, request.user)
        elif fmt == 'json':
            imported, skipped = _import_json(zip_file, project, request.user)
        else:
            messages.error(request, 'Unknown format.')
            return redirect(request.path)
    except Exception as exc:
        messages.error(request, f'Import failed: {exc}')
        return redirect(request.path)

    log_activity(project, request.user, 'image_uploaded',
                 detail=f'{imported} image(s) imported ({fmt.upper()})')
    if imported:
        messages.success(request, f'Imported {imported} image(s) into "{project.name}".')
    if skipped:
        messages.warning(request, f'{skipped} file(s) skipped (unsupported type or error).')
    return redirect('project_images', project_id=project.id)


# ── Import helpers ─────────────────────────────────────────────────────────────

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}


def _save_image_from_bytes(data, filename, project, user):
    """Create an Image object from raw bytes. Returns the Image or raises."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in IMAGE_EXTS:
        raise ValueError(f'Unsupported image type: {ext}')
    cf = ContentFile(data, name=filename)
    img_obj = Image(project=project, uploaded_by=user,
                    file_size=len(data), name=filename)
    img_obj.image_file.save(filename, cf, save=True)
    return img_obj


def _get_or_create_tag(name, user):
    tag, _ = Tag.objects.get_or_create(
        name=name,
        defaults={'created_by': user, 'color': '#6366f1'},
    )
    return tag


def _import_yolo(zip_file, project, user):
    imported = skipped = 0
    with zipfile.ZipFile(zip_file) as zf:
        names = zf.namelist()

        # Load classes
        classes = []
        for n in names:
            if os.path.basename(n) == 'classes.txt' or os.path.basename(n) == 'data.yaml':
                raw = zf.read(n).decode('utf-8', errors='ignore')
                if n.endswith('.yaml'):
                    for line in raw.splitlines():
                        if line.strip().startswith('names'):
                            part = line.split(':', 1)[1].strip()
                            try:
                                import ast
                                classes = ast.literal_eval(part)
                            except Exception:
                                pass
                            break
                else:
                    classes = [l.strip() for l in raw.splitlines() if l.strip()]
                break

        # Find images
        image_entries = [n for n in names
                         if os.path.splitext(n)[1].lower() in IMAGE_EXTS
                         and not os.path.basename(n).startswith('.')]

        for img_path in image_entries:
            filename = os.path.basename(img_path)
            stem = os.path.splitext(filename)[0]
            try:
                data = zf.read(img_path)
                img_obj = _save_image_from_bytes(data, filename, project, user)
            except Exception:
                skipped += 1
                continue

            # Find matching label file
            label_path = None
            for n in names:
                if os.path.basename(n) == f'{stem}.txt' and 'label' in n.lower():
                    label_path = n
                    break
            if label_path is None:
                for n in names:
                    if os.path.basename(n) == f'{stem}.txt':
                        label_path = n
                        break

            if label_path:
                try:
                    label_text = zf.read(label_path).decode('utf-8', errors='ignore')
                    has_annotations = False
                    for line in label_text.strip().splitlines():
                        parts = line.strip().split()
                        if len(parts) == 5:
                            cls_idx, x_c, y_c, w, h = int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                            label_name = classes[cls_idx] if cls_idx < len(classes) else f'class_{cls_idx}'
                            tag = _get_or_create_tag(label_name, user)
                            x = (x_c - w / 2) * 100
                            y = (y_c - h / 2) * 100
                            BoundingBox.objects.create(
                                image=img_obj, label=tag, created_by=user,
                                x=round(x, 4), y=round(y, 4),
                                width=round(w * 100, 4), height=round(h * 100, 4),
                            )
                            has_annotations = True
                        elif len(parts) >= 5 and len(parts) % 2 == 1:
                            cls_idx = int(parts[0])
                            label_name = classes[cls_idx] if cls_idx < len(classes) else f'class_{cls_idx}'
                            tag = _get_or_create_tag(label_name, user)
                            coords = [float(v) for v in parts[1:]]
                            points = [{'x': coords[i] * 100, 'y': coords[i+1] * 100}
                                      for i in range(0, len(coords), 2)]
                            if len(points) >= 3:
                                Polygon.objects.create(
                                    image=img_obj, label=tag, created_by=user, points=points)
                                has_annotations = True
                    if has_annotations:
                        img_obj.status = 'partial'
                        img_obj.save(update_fields=['status'])
                except Exception:
                    pass

            imported += 1
    return imported, skipped


def _import_coco(zip_file, project, user):
    imported = skipped = 0
    with zipfile.ZipFile(zip_file) as zf:
        names = zf.namelist()

        # Find annotation JSON
        ann_path = None
        for n in names:
            if n.endswith('.json') and 'annotation' in n.lower():
                ann_path = n
                break
        if ann_path is None:
            for n in names:
                if n.endswith('.json'):
                    ann_path = n
                    break

        coco = {}
        if ann_path:
            try:
                coco = json.loads(zf.read(ann_path).decode('utf-8'))
            except Exception:
                pass

        # Build maps
        cat_map = {c['id']: c['name'] for c in coco.get('categories', [])}
        coco_img_map = {i['id']: i for i in coco.get('images', [])}
        ann_by_img = {}
        for ann in coco.get('annotations', []):
            ann_by_img.setdefault(ann['image_id'], []).append(ann)

        # Import images
        image_entries = [n for n in names
                         if os.path.splitext(n)[1].lower() in IMAGE_EXTS
                         and not os.path.basename(n).startswith('.')]

        filename_to_coco_id = {}
        for coco_img in coco_img_map.values():
            fname = os.path.basename(coco_img.get('file_name', ''))
            filename_to_coco_id[fname] = coco_img['id']

        for img_path in image_entries:
            filename = os.path.basename(img_path)
            try:
                data = zf.read(img_path)
                img_obj = _save_image_from_bytes(data, filename, project, user)
            except Exception:
                skipped += 1
                continue

            coco_id = filename_to_coco_id.get(filename)
            coco_meta = coco_img_map.get(coco_id, {})
            img_w = coco_meta.get('width', 1024) or 1024
            img_h = coco_meta.get('height', 1024) or 1024
            annotations = ann_by_img.get(coco_id, [])
            has_ann = False

            for ann in annotations:
                cat_name = cat_map.get(ann.get('category_id', 0), 'unknown')
                tag = _get_or_create_tag(cat_name, user)
                seg = ann.get('segmentation', [])
                bbox = ann.get('bbox')

                if seg and isinstance(seg, list) and seg[0]:
                    coords = seg[0]
                    points = [{'x': coords[i] / img_w * 100, 'y': coords[i+1] / img_h * 100}
                              for i in range(0, len(coords) - 1, 2)]
                    if len(points) >= 3:
                        Polygon.objects.create(image=img_obj, label=tag, created_by=user, points=points)
                        has_ann = True
                elif bbox and len(bbox) == 4:
                    x, y, w, h = bbox
                    BoundingBox.objects.create(
                        image=img_obj, label=tag, created_by=user,
                        x=round(x / img_w * 100, 4), y=round(y / img_h * 100, 4),
                        width=round(w / img_w * 100, 4), height=round(h / img_h * 100, 4),
                    )
                    has_ann = True

            if has_ann:
                img_obj.status = 'partial'
                img_obj.save(update_fields=['status'])
            imported += 1
    return imported, skipped


def _import_csv(zip_file, project, user):
    import csv as csv_mod
    imported = skipped = 0
    with zipfile.ZipFile(zip_file) as zf:
        names = zf.namelist()

        csv_path = None
        for n in names:
            if n.endswith('.csv'):
                csv_path = n
                break

        rows_by_name = {}
        if csv_path:
            try:
                text = zf.read(csv_path).decode('utf-8', errors='ignore')
                reader = csv_mod.DictReader(io.StringIO(text))
                for row in reader:
                    rows_by_name.setdefault(row.get('image_name', ''), []).append(row)
            except Exception:
                pass

        image_entries = [n for n in names
                         if os.path.splitext(n)[1].lower() in IMAGE_EXTS
                         and not os.path.basename(n).startswith('.')]

        for img_path in image_entries:
            filename = os.path.basename(img_path)
            try:
                data = zf.read(img_path)
                img_obj = _save_image_from_bytes(data, filename, project, user)
            except Exception:
                skipped += 1
                continue

            rows = rows_by_name.get(filename, [])
            has_ann = False
            for row in rows:
                ann_type = row.get('annotation_type', '')
                label_name = row.get('label', '').strip()
                if not label_name:
                    continue
                tag = _get_or_create_tag(label_name, user)
                try:
                    if ann_type == 'bbox':
                        BoundingBox.objects.create(
                            image=img_obj, label=tag, created_by=user,
                            x=float(row['x']), y=float(row['y']),
                            width=float(row['width']), height=float(row['height']),
                        )
                        has_ann = True
                    elif ann_type == 'polygon':
                        points = [
                            {'x': float(p.split(',')[0]), 'y': float(p.split(',')[1])}
                            for p in row.get('points', '').split(';') if ',' in p
                        ]
                        if len(points) >= 3:
                            Polygon.objects.create(image=img_obj, label=tag, created_by=user, points=points)
                            has_ann = True
                except Exception:
                    continue

            if has_ann:
                img_obj.status = 'partial'
                img_obj.save(update_fields=['status'])
            imported += 1
    return imported, skipped


def _import_json(zip_file, project, user):
    imported = skipped = 0
    with zipfile.ZipFile(zip_file) as zf:
        names = zf.namelist()

        json_path = None
        for n in names:
            if n.endswith('.json') and 'annotation' in n.lower():
                json_path = n
                break
        if json_path is None:
            for n in names:
                if n.endswith('.json'):
                    json_path = n
                    break

        img_data_map = {}
        if json_path:
            try:
                data = json.loads(zf.read(json_path).decode('utf-8'))
                for entry in data.get('images', []):
                    img_data_map[entry.get('name', '')] = entry
            except Exception:
                pass

        image_entries = [n for n in names
                         if os.path.splitext(n)[1].lower() in IMAGE_EXTS
                         and not os.path.basename(n).startswith('.')]

        for img_path in image_entries:
            filename = os.path.basename(img_path)
            try:
                raw = zf.read(img_path)
                img_obj = _save_image_from_bytes(raw, filename, project, user)
            except Exception:
                skipped += 1
                continue

            entry = img_data_map.get(filename, {})
            has_ann = False
            for box in entry.get('bounding_boxes', []):
                label_name = box.get('label') or ''
                if not label_name:
                    continue
                tag = _get_or_create_tag(label_name, user)
                try:
                    BoundingBox.objects.create(
                        image=img_obj, label=tag, created_by=user,
                        x=float(box['x']), y=float(box['y']),
                        width=float(box['width']), height=float(box['height']),
                    )
                    has_ann = True
                except Exception:
                    continue
            for poly in entry.get('polygons', []):
                label_name = poly.get('label') or ''
                if not label_name:
                    continue
                tag = _get_or_create_tag(label_name, user)
                points = poly.get('points', [])
                if len(points) >= 3:
                    Polygon.objects.create(image=img_obj, label=tag, created_by=user, points=points)
                    has_ann = True

            if has_ann:
                img_obj.status = 'partial'
                img_obj.save(update_fields=['status'])
            imported += 1
    return imported, skipped


@login_required
def image_comment(request, image_id):
    """POST  → add comment; DELETE ?comment_id=N → delete own comment."""
    image = get_object_or_404(Image, pk=image_id)
    if not image.project.user_has_access(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if request.method == 'POST':
        data = json.loads(request.body or '{}')
        body = data.get('body', '').strip()
        if not body:
            return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)
        if len(body) > 2000:
            return JsonResponse({'error': 'Comment too long (max 2 000 chars).'}, status=400)

        comment = ImageComment.objects.create(image=image, author=request.user, body=body)
        d = comment.to_dict()
        d['can_delete'] = True
        return JsonResponse({'comment': d}, status=201)

    if request.method == 'DELETE':
        comment_id = request.GET.get('comment_id')
        comment = get_object_or_404(ImageComment, pk=comment_id, image=image)
        if comment.author != request.user and not image.project.user_is_admin(request.user):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        comment.delete()
        return JsonResponse({'deleted': True})

    return JsonResponse({'error': 'Method not allowed'}, status=405)