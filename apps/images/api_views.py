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

from .models import Image, APIToken
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