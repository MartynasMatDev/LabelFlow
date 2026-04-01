from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    ANNOTATION_TYPE_CHOICES = [
        ('bbox', 'Bounding Box'),
        ('polygon', 'Poligon'),
        ('classification', 'Classification'),
        ('mixed', 'Mixed'),
    ]

    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    annotation_type = models.CharField(max_length=20, choices=ANNOTATION_TYPE_CHOICES, default='bbox')
    emoji           = models.CharField(max_length=4, default='◈')
    created_by      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    is_archived     = models.BooleanField(default=False, db_index=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def get_user_role(self, user):
        membership = self.members.filter(user=user).first()
        return membership.role if membership else None

    def user_has_access(self, user):
        return self.members.filter(user=user).exists() or self.created_by == user

    def user_is_admin(self, user):
        if self.created_by == user:
            return True
        membership = self.members.filter(user=user).first()
        return membership and membership.role == 'admin'

    @property
    def image_count(self):
        return self.images.count()

    @property
    def member_count(self):
        return self.members.count()

    def archive(self):
        self.is_archived = True
        self.save(update_fields=['is_archived', 'updated_at'])

    def restore(self):
        self.is_archived = False
        self.save(update_fields=['is_archived', 'updated_at'])


class ProjectMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('annotator', 'Annotator'),
        ('viewer', 'Reviewer'),
    ]
    project   = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members')
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    role      = models.CharField(max_length=20, choices=ROLE_CHOICES, default='annotator')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('project', 'user')
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user.username} — {self.project.name} ({self.get_role_display()})"

    def get_initials(self):
        first = self.user.first_name[:1].upper() if self.user.first_name else ''
        last  = self.user.last_name[:1].upper()  if self.user.last_name  else ''
        return (first + last) or self.user.username[:2].upper()


class ActivityLog(models.Model):
    """Tracks all user activity within a project."""

    ACTION_CHOICES = [
        # Images
        ('image_uploaded',    'Uploaded image'),
        ('image_deleted',     'Deleted image'),
        # Annotations
        ('annotation_saved',  'Saved annotations'),
        ('annotation_done',   'Marked as done'),
        # Tags
        ('tag_added',         'Added tag'),
        ('tag_removed',       'Removed tag'),
        # Team
        ('member_added',      'Added member'),
        ('member_removed',    'Removed member'),
        ('role_changed',      'Changed role'),
        # Project
        ('project_created',   'Created project'),
        ('project_archived',  'Archived project'),
        ('project_restored',  'Restored project'),
    ]

    project    = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activity_logs')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activity_logs')
    action     = models.CharField(max_length=40, choices=ACTION_CHOICES)
    # Human-readable detail (e.g. image name, member username)
    detail     = models.CharField(max_length=500, blank=True)
    # Optional JSON metadata for future use
    meta       = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        username = self.user.username if self.user else 'Unknown'
        return f"[{self.project.name}] {username}: {self.get_action_display()}"

    def get_initials(self):
        if not self.user:
            return '??'
        first = self.user.first_name[:1].upper() if self.user.first_name else ''
        last  = self.user.last_name[:1].upper()  if self.user.last_name  else ''
        return (first + last) or self.user.username[:2].upper()

    @property
    def actor_name(self):
        if not self.user:
            return 'Unknown user'
        return self.user.get_full_name() or self.user.username

    ACTION_ICONS = {
        'image_uploaded':   '↑',
        'image_deleted':    '✕',
        'annotation_saved': '✎',
        'annotation_done':  '✓',
        'tag_added':        '⬡',
        'tag_removed':      '⬡',
        'member_added':     '⬔',
        'member_removed':   '⬔',
        'role_changed':     '⬔',
        'project_created':  '◈',
        'project_archived': '▣',
        'project_restored': '◈',
    }

    ACTION_COLORS = {
        'image_uploaded':   'accent',
        'image_deleted':    'danger',
        'annotation_saved': 'success',
        'annotation_done':  'success',
        'tag_added':        'warning',
        'tag_removed':      'warning',
        'member_added':     'accent',
        'member_removed':   'danger',
        'role_changed':     'warning',
        'project_created':  'accent',
        'project_archived': 'warning',
        'project_restored': 'success',
    }

    @property
    def icon(self):
        return self.ACTION_ICONS.get(self.action, '·')

    @property
    def color_class(self):
        return self.ACTION_COLORS.get(self.action, 'accent')
