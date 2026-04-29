"""Helpers for the 'active workspace' concept.

The active workspace lives in the session under SESSION_KEY. It is the
scope the user is currently operating in — creating a project, listing
projects, uploading images etc. all default to the active workspace.
"""
from django.db.models import Q

from .models import Workspace


SESSION_KEY = 'active_workspace_id'


def workspaces_for(user):
    """All workspaces the given user can access: their owned ones plus
    any organization workspaces they've been added to."""
    if not user.is_authenticated:
        return Workspace.objects.none()
    return (
        Workspace.objects
        .filter(Q(owner=user) | Q(members__user=user))
        .distinct()
    )


def get_personal_workspace(user):
    """Return (and lazily create) the user's personal workspace.

    The signup signal normally creates this, but pre-existing users or
    edge cases (e.g. tests that bypass signals) may not have one yet."""
    ws = Workspace.objects.filter(owner=user, kind=Workspace.KIND_PERSONAL).first()
    if ws:
        return ws
    name = (user.get_full_name() or user.username or 'Personal').strip()
    return Workspace.objects.create(
        owner=user,
        name=f"{name}'s workspace",
        kind=Workspace.KIND_PERSONAL,
    )


def get_active_workspace(request):
    """Return the user's current active workspace, or None if anonymous.

    Falls back to the personal workspace if the session value is stale
    or the user has lost access to it."""
    user = request.user
    if not user.is_authenticated:
        return None

    ws_id = request.session.get(SESSION_KEY)
    if ws_id:
        ws = Workspace.objects.filter(pk=ws_id).first()
        if ws and ws.user_has_access(user):
            return ws
        # Stale — clear it.
        request.session.pop(SESSION_KEY, None)

    ws = get_personal_workspace(user)
    request.session[SESSION_KEY] = ws.pk
    return ws


def set_active_workspace(request, workspace):
    request.session[SESSION_KEY] = workspace.pk


def active_workspace_context(request):
    """Template context processor — exposes `active_workspace` and
    `user_workspaces` to every template."""
    if not request.user.is_authenticated:
        return {}
    active = get_active_workspace(request)
    return {
        'active_workspace': active,
        'user_workspaces': list(workspaces_for(request.user)),
    }
