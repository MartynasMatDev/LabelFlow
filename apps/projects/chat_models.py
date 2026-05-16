"""Chat models for project-based team communication."""
from django.db import models
from django.contrib.auth.models import User


class ChatRoom(models.Model):
    """One chat room per project."""
    project = models.OneToOneField(
        'projects.Project',          # string ref avoids circular import
        on_delete=models.CASCADE,
        related_name='chat_room',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat: {self.project.name}"

    @classmethod
    def get_or_create_for_project(cls, project):
        room, _ = cls.objects.get_or_create(project=project)
        return room


class ChatMessage(models.Model):
    """A single message in a project chat room."""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username}: {self.body[:50]}"

    def to_dict(self):
        return {
            'id': self.id,
            'author': self.author.get_full_name() or self.author.username,
            'author_initials': self._get_initials(self.author),
            'author_id': self.author_id,
            'body': self.body,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'created_at_iso': self.created_at.isoformat(),
        }

    @staticmethod
    def _get_initials(user):
        first = user.first_name[:1].upper() if user.first_name else ''
        last = user.last_name[:1].upper() if user.last_name else ''
        return (first + last) or user.username[:2].upper()