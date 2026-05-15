"""
apps/images/api_views.py
REST API endpoint for image uploads.

POST /app/images/api/upload/
    Content-Type: multipart/form-data

Required fields
    image_file  – the image binary (multipart file field)
    project     – integer project PK

Optional fields
    (none at the moment; tags can be added later)

Authentication
    Session-based (cookie) – works for browser / same-origin clients.
    Token-based            – pass  Authorization: Token <key>  header.
                             Tokens are created via POST /app/images/api/token/.

Responses
    201  { "id", "name", "url", "project_id", "status",
           "width", "height", "file_size_bytes", "file_size_kb",
           "resolution", "uploaded_at", "uploaded_by" }
    400  { "error": "<reason>" }
    401  { "error": "Authentication required." }
    403  { "error": "You do not have access to this project." }
    404  { "error": "Project not found." }
    405  { "error": "Method not allowed. Use POST." }
"""

import os
import json
import secrets
import hashlib

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.projects.models import Project
from apps.projects.activity import log_activity

from .models import Image, APIToken, Tag, BoundingBox, Polygon, SegmentationMask
from .views import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
    _normalise_upload,
)


# ─── Token helpers ────────────────────────────────────────────────────────────

def _get_token_user(request):
    """
    Return the User associated with a Bearer / Token auth header, or None.
    Supports both:
        Authorization: Token <key>
        Authorization: Bearer <key>
    """
    header = request.META.get("HTTP_AUTHORIZATION", "").strip()
    if not header:
        return None

    parts = header.split()
    if len(parts) != 2 or parts[0].lower() not in ("token", "bearer"):
        return None

    raw_key = parts[1]
    try:
        token = APIToken.objects.select_related("user").get(
            key=APIToken.hash_key(raw_key),
            is_active=True,
        )
        return token.user
    except APIToken.DoesNotExist:
        return None


def _resolve_user(request):
    """
    Return the authenticated User from session OR Authorization header.
    Returns None when no valid identity is found.
    """
    if request.user.is_authenticated:
        return request.user
    return _get_token_user(request)


# ─── Main upload endpoint ─────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_image_upload(request):
    """
    POST /app/images/api/upload/

    Upload a single image file and attach it to a project.
    Accepts multipart/form-data with fields:
        image_file  (required) – the image binary
        project     (required) – integer project PK
    """
    # ── 1. Authentication ──────────────────────────────────────────────────
    user = _resolve_user(request)
    if user is None:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    # ── 2. Project lookup & access ─────────────────────────────────────────
    project_id = request.POST.get("project", "").strip()
    if not project_id:
        return JsonResponse(
            {"error": "Missing required field: 'project'."},
            status=400,
        )

    try:
        project = Project.objects.get(pk=project_id)
    except (Project.DoesNotExist, ValueError):
        return JsonResponse({"error": "Project not found."}, status=404)

    if not project.user_has_access(user):
        return JsonResponse(
            {"error": "You do not have access to this project."},
            status=403,
        )

    # ── 3. File presence check ─────────────────────────────────────────────
    f = request.FILES.get("image_file")
    if f is None:
        return JsonResponse(
            {"error": "No file provided. Send an image as 'image_file' (multipart/form-data)."},
            status=400,
        )

    # ── 4. Extension / format validation ──────────────────────────────────
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse(
            {
                "error": (
                    f"Unsupported file type '{ext}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
                )
            },
            status=400,
        )

    # ── 5. Size validation ─────────────────────────────────────────────────
    if f.size > MAX_FILE_BYTES:
        limit_mb = MAX_FILE_BYTES // (1024 * 1024)
        return JsonResponse(
            {"error": f"File too large. Maximum allowed size is {limit_mb} MB."},
            status=400,
        )

    # ── 6. Image integrity check & normalisation ───────────────────────────
    try:
        normalised = _normalise_upload(f, f.name)
    except Exception as exc:
        return JsonResponse(
            {"error": f"File is not a valid image or could not be processed: {exc}"},
            status=400,
        )

    # ── 7. Persist ─────────────────────────────────────────────────────────
    image = Image.objects.create(
        project=project,
        uploaded_by=user,
        image_file=normalised,
        name=normalised.name,
        file_size=normalised.size,
    )

    log_activity(project, user, "image_uploaded", detail=image.name)

    # ── 8. Success response ────────────────────────────────────────────────
    return JsonResponse(_image_to_dict(image, request), status=201)


# ─── Token management endpoints ───────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def api_token_create(request):
    """
    POST /app/images/api/token/

    Obtain an API token using username + password credentials.
    Body (JSON or form-encoded):
        username, password

    Response 200  { "token": "<plaintext key>", "username": "..." }
    Response 400  { "error": "..." }
    Response 401  { "error": "Invalid credentials." }
    """
    # Parse body – accept JSON or form-encoded
    if request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body)
        except ValueError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)
    else:
        body = request.POST

    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        return JsonResponse(
            {"error": "Both 'username' and 'password' are required."},
            status=400,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid credentials."}, status=401)

    # Create (or rotate) a token for this user
    raw_key = secrets.token_hex(32)          # 256-bit random token
    hashed  = APIToken.hash_key(raw_key)

    APIToken.objects.filter(user=user).update(is_active=False)   # revoke old tokens
    APIToken.objects.create(user=user, key=hashed)

    return JsonResponse({"token": raw_key, "username": user.username})


@csrf_exempt
@require_http_methods(["DELETE"])
def api_token_revoke(request):
    """
    DELETE /app/images/api/token/

    Revoke the token supplied in the Authorization header.
    """
    user = _get_token_user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)

    revoked = APIToken.objects.filter(user=user, is_active=True).update(is_active=False)
    return JsonResponse({"revoked": revoked > 0})


# ─── Helper ───────────────────────────────────────────────────────────────────

def _image_to_dict(image, request):
    """Serialise an Image instance to a dict suitable for JSON responses."""
    url = request.build_absolute_uri(image.image_file.url) if image.image_file else None
    return {
        "id":              image.pk,
        "name":            image.name,
        "url":             url,
        "project_id":      image.project_id,
        "status":          image.status,
        "width":           image.width,
        "height":          image.height,
        "file_size_bytes": image.file_size,
        "file_size_kb":    image.file_size_kb,
        "resolution":      image.resolution,
        "uploaded_at":     image.uploaded_at.isoformat(),
        "uploaded_by":     image.uploaded_by.username if image.uploaded_by else None,
    }
# ─── ANNOTATION API ───────────────────────────────────────────────────────────
#
# Append these imports to the existing import block at the top of api_views.py:
#
#   from .models import Image, APIToken, Tag, BoundingBox, Polygon, SegmentationMask
#
# Then append the functions below to the bottom of api_views.py.
#
# New endpoints (add to urls.py):
#   POST /app/images/api/images/<image_id>/annotations/
#   GET  /app/images/api/images/<image_id>/annotations/
#   DELETE /app/images/api/annotations/<annotation_type>/<annotation_id>/
# ─────────────────────────────────────────────────────────────────────────────


@csrf_exempt
def api_annotations(request, image_id):
    """
    GET  – list all annotations for an image
    POST – create a new annotation on an image

    URL: /app/images/api/images/<image_id>/annotations/

    POST body (JSON):
    {
        "type": "bbox" | "polygon" | "mask",
        "label_id": <int | null>,

        // bbox only:
        "x": 10.5,       // left edge, 0–100 (% of image width)
        "y": 20.0,       // top edge,  0–100 (% of image height)
        "width": 30.0,   // 0–100
        "height": 25.0,  // 0–100

        // polygon only:
        "points": [{"x": 10.0, "y": 20.0}, ...],   // min 3 points

        // mask only:
        "mask_data": "data:image/png;base64,..."
    }
    """
    user = _resolve_user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)

    image = _get_image_or_403(image_id, user)
    if isinstance(image, JsonResponse):
        return image

    if request.method == "GET":
        return _list_annotations(image)

    if request.method == "POST":
        return _create_annotation(request, image, user)

    return JsonResponse({"error": "Method not allowed. Use GET or POST."}, status=405)


@csrf_exempt
def api_annotation_delete(request, annotation_type, annotation_id):
    """
    DELETE /app/images/api/annotations/<annotation_type>/<annotation_id>/

    annotation_type: bbox | polygon | mask
    """
    if request.method != "DELETE":
        return JsonResponse({"error": "Method not allowed. Use DELETE."}, status=405)

    user = _resolve_user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)

    model_map = {
        "bbox":    BoundingBox,
        "polygon": Polygon,
        "mask":    SegmentationMask,
    }
    if annotation_type not in model_map:
        return JsonResponse(
            {"error": f"Unknown annotation type '{annotation_type}'. Use: bbox, polygon, mask."},
            status=400,
        )

    Model = model_map[annotation_type]
    try:
        obj = Model.objects.select_related("image__project").get(pk=annotation_id)
    except Model.DoesNotExist:
        return JsonResponse({"error": "Annotation not found."}, status=404)

    if not obj.image.project.user_has_access(user):
        return JsonResponse({"error": "You do not have access to this project."}, status=403)

    obj.delete()
    _update_image_status(obj.image)
    return JsonResponse({"deleted": True, "type": annotation_type, "id": annotation_id})


# ─── Private helpers ──────────────────────────────────────────────────────────

def _get_image_or_403(image_id, user):
    """Return Image or a JsonResponse error."""
    try:
        image = Image.objects.select_related("project").get(pk=image_id)
    except (Image.DoesNotExist, ValueError):
        return JsonResponse({"error": "Image not found."}, status=404)

    if not image.project.user_has_access(user):
        return JsonResponse({"error": "You do not have access to this project."}, status=403)

    return image


def _list_annotations(image):
    """Return all annotations for an image as JSON."""
    data = {
        "image_id":   image.pk,
        "image_name": image.name,
        "status":     image.status,
        "bboxes":     [b.to_dict() for b in image.bounding_boxes.select_related("label").all()],
        "polygons":   [p.to_dict() for p in image.polygons.select_related("label").all()],
        "masks":      [m.to_meta() for m in image.seg_masks.select_related("label").all()],
    }
    return JsonResponse(data)


def _create_annotation(request, image, user):
    """Parse the POST body and create the correct annotation type."""
    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    ann_type = body.get("type", "").strip().lower()
    if ann_type not in ("bbox", "polygon", "mask"):
        return JsonResponse(
            {"error": "Missing or invalid 'type'. Must be one of: bbox, polygon, mask."},
            status=400,
        )

    # Resolve optional label
    label = None
    label_id = body.get("label_id")
    if label_id is not None:
        try:
            label = Tag.objects.get(pk=label_id)
        except Tag.DoesNotExist:
            return JsonResponse({"error": f"Label with id {label_id} not found."}, status=400)

    if ann_type == "bbox":
        return _create_bbox(body, image, label, user)
    if ann_type == "polygon":
        return _create_polygon(body, image, label, user)
    return _create_mask(body, image, label, user)


def _create_bbox(body, image, label, user):
    errors = []
    fields = {}
    for field in ("x", "y", "width", "height"):
        val = body.get(field)
        if val is None:
            errors.append(f"'{field}' is required for bbox annotations.")
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            errors.append(f"'{field}' must be a number.")
            continue
        if not (0.0 <= fval <= 100.0):
            errors.append(f"'{field}' must be between 0 and 100 (percentage).")
        fields[field] = fval

    if errors:
        return JsonResponse({"error": errors}, status=400)

    box = BoundingBox.objects.create(
        image=image, label=label, created_by=user, **fields
    )
    _update_image_status(image)
    _log(image, user, "bbox")
    return JsonResponse({"type": "bbox", "annotation": box.to_dict()}, status=201)


def _create_polygon(body, image, label, user):
    points = body.get("points")
    if not points or not isinstance(points, list):
        return JsonResponse(
            {"error": "'points' is required for polygon annotations and must be a list."},
            status=400,
        )
    if len(points) < 3:
        return JsonResponse(
            {"error": "A polygon must have at least 3 points."},
            status=400,
        )
    for i, pt in enumerate(points):
        if not isinstance(pt, dict) or "x" not in pt or "y" not in pt:
            return JsonResponse(
                {"error": f"Point {i} must be an object with 'x' and 'y' keys."},
                status=400,
            )
        try:
            px, py = float(pt["x"]), float(pt["y"])
        except (TypeError, ValueError):
            return JsonResponse(
                {"error": f"Point {i} 'x' and 'y' must be numbers."},
                status=400,
            )
        if not (0.0 <= px <= 100.0) or not (0.0 <= py <= 100.0):
            return JsonResponse(
                {"error": f"Point {i} coordinates must be between 0 and 100 (percentage)."},
                status=400,
            )
        points[i] = {"x": px, "y": py}

    poly = Polygon.objects.create(
        image=image, label=label, created_by=user, points=points
    )
    _update_image_status(image)
    _log(image, user, "polygon")
    return JsonResponse({"type": "polygon", "annotation": poly.to_dict()}, status=201)


def _create_mask(body, image, label, user):
    mask_data = body.get("mask_data", "").strip()
    if not mask_data:
        return JsonResponse(
            {"error": "'mask_data' is required for mask annotations (base64-encoded PNG data URI)."},
            status=400,
        )
    if not mask_data.startswith("data:image/png;base64,"):
        return JsonResponse(
            {"error": "'mask_data' must be a PNG data URI starting with 'data:image/png;base64,'."},
            status=400,
        )

    mask = SegmentationMask.objects.create(
        image=image, label=label, created_by=user, mask_data=mask_data
    )
    _update_image_status(image)
    _log(image, user, "mask")
    return JsonResponse({"type": "mask", "annotation": mask.to_dict()}, status=201)


def _update_image_status(image):
    """Recalculate and save image annotation status."""
    has_any = (
        image.bounding_boxes.exists()
        or image.polygons.exists()
        or image.seg_masks.exists()
    )
    image.status = "partial" if has_any else "pending"
    image.save(update_fields=["status"])


def _log(image, user, ann_type):
    try:
        log_activity(image.project, user, "annotation_added", detail=f"{ann_type} on {image.name}")
    except Exception:
        pass