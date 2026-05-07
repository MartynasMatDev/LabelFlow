"""Notification views, helpers, and template context processor."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Notification


NOTIFICATION_ICONS = {
    'member_added':     'fa-user-plus',
    'member_removed':   'fa-user-minus',
    'role_changed':     'fa-user-pen',
    'image_uploaded':   'fa-image',
    'image_deleted':    'fa-trash',
    'annotation_done':  'fa-check',
    'annotation_saved': 'fa-pen',
    'tag_added':        'fa-tag',
    'tag_removed':      'fa-tag',
    'project_created':  'fa-folder-plus',
    'project_archived': 'fa-box-archive',
    'project_restored': 'fa-rotate-left',
    'comment':          'fa-comment',
}

NOTIFICATION_VERBS = {
    'member_added':     'added a teammate',
    'member_removed':   'removed a teammate',
    'role_changed':     'changed a role',
    'image_uploaded':   'uploaded an image',
    'image_deleted':    'deleted an image',
    'annotation_done':  'marked an image done',
    'annotation_saved': 'saved annotations',
    'tag_added':        'added a tag',
    'tag_removed':      'removed a tag',
    'project_created':  'created the project',
    'project_archived': 'archived the project',
    'project_restored': 'restored the project',
    'comment':          'left a comment',
}


def _decorate(notif):
    notif.icon = NOTIFICATION_ICONS.get(notif.kind, 'fa-bell')
    notif.verb = NOTIFICATION_VERBS.get(notif.kind, notif.get_kind_display())
    return notif


def notifications_context(request):
    """Expose unread count + a small recent slice to every template."""
    if not request.user.is_authenticated:
        return {}
    qs = Notification.objects.filter(recipient=request.user)
    recent = list(qs[:8])
    for n in recent:
        _decorate(n)
    return {
        'notification_unread_count': qs.filter(is_read=False).count(),
        'notification_recent': recent,
    }


@login_required
def notifications_list(request):
    qs = Notification.objects.filter(recipient=request.user).select_related('actor', 'project')
    notifications = [_decorate(n) for n in qs[:100]]
    return render(request, 'app/notifications.html', {
        'notifications': notifications,
        'active_nav': 'notifications',
    })


@login_required
def notifications_unread_json(request):
    qs = Notification.objects.filter(recipient=request.user, is_read=False)
    return JsonResponse({'unread': qs.count()})


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    notif = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=['is_read'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect(notif.url or 'notifications_list')


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('notifications_list')
