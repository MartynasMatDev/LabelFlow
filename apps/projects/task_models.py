"""Task management models for project assignments."""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.projects.models import Project
from apps.images.models import Image  # Import Image directly


class Task(models.Model):
    """A task assigned to a team member for a project."""

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')

    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional: link to specific images - use the imported Image model directly
    related_images = models.ManyToManyField(Image, blank=True, related_name='tasks')

    class Meta:
        ordering = ['-priority', 'due_date', '-created_at']

    def __str__(self):
        return f"{self.title} - {self.assigned_to.username}"

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return timezone.now() > self.due_date
        return False

    @property
    def priority_color(self):
        colors = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'urgent': 'danger',
        }
        return colors.get(self.priority, 'secondary')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assigned_to': {
                'id': self.assigned_to.id,
                'name': self.assigned_to.get_full_name() or self.assigned_to.username,
                'initials': self._get_initials(self.assigned_to),
            },
            'assigned_by_name': self.assigned_by.get_full_name() or self.assigned_by.username if self.assigned_by else 'Unknown',
            'priority': self.priority,
            'priority_label': self.get_priority_display(),
            'priority_color': self.priority_color,
            'status': self.status,
            'status_label': self.get_status_display(),
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'due_date_formatted': self.due_date.strftime('%Y-%m-%d %H:%M') if self.due_date else None,
            'is_overdue': self.is_overdue,
            'created_at': self.created_at.isoformat(),
            'created_at_formatted': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }

    @staticmethod
    def _get_initials(user):
        if not user:
            return '??'
        first = user.first_name[:1].upper() if user.first_name else ''
        last = user.last_name[:1].upper() if user.last_name else ''
        return (first + last) or user.username[:2].upper()


class TaskComment(models.Model):
    """Comments on tasks for communication."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_comments')
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.task.title} by {self.author.username}"

    def to_dict(self):
        return {
            'id': self.id,
            'author': self.author.get_full_name() or self.author.username,
            'author_initials': self._get_initials(self.author),
            'body': self.body,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
        }

    @staticmethod
    def _get_initials(user):
        first = user.first_name[:1].upper() if user.first_name else ''
        last = user.last_name[:1].upper() if user.last_name else ''
        return (first + last) or user.username[:2].upper()