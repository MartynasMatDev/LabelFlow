"""Views for project-based team chat."""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from .models import Project
from .chat_models import ChatRoom, ChatMessage


@login_required
@require_http_methods(['GET', 'POST'])
def chat_room(request, project_id):
    """
    GET  /app/project/<id>/chat/          → last 100 messages (JSON)
    GET  /app/project/<id>/chat/?since=<id> → messages after that id (JSON, for polling)
    POST /app/project/<id>/chat/          → send a message
    """
    project = get_object_or_404(Project, id=project_id)
    if not project.user_has_access(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)

    room = ChatRoom.get_or_create_for_project(project)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            body = data.get('body', '').strip()
            if not body:
                return JsonResponse({'error': 'Message cannot be empty'}, status=400)
            if len(body) > 2000:
                return JsonResponse({'error': 'Message too long (max 2000 chars)'}, status=400)

            msg = ChatMessage.objects.create(room=room, author=request.user, body=body)
            return JsonResponse({'success': True, 'message': msg.to_dict()})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # GET — return messages, optionally filtered by since_id for polling
    since_id = request.GET.get('since')
    qs = room.messages.select_related('author')

    if since_id:
        try:
            qs = qs.filter(id__gt=int(since_id))
        except (ValueError, TypeError):
            pass
    else:
        qs = qs.order_by('-created_at')[:100]
        qs = list(reversed(list(qs)))  # chronological order

    messages_data = [m.to_dict() for m in qs]
    return JsonResponse({
        'messages': messages_data,
        'current_user_id': request.user.id,
    })