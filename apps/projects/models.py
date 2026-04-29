from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from django.utils.text import slugify


class Workspace(models.Model):
    """A container for projects. Can be personal (single-user) or an
    organization shared by a team."""

    KIND_PERSONAL = 'personal'
    KIND_ORGANIZATION = 'organization'
    KIND_CHOICES = [
        (KIND_PERSONAL, 'Personal'),
        (KIND_ORGANIZATION, 'Organization'),
    ]

    name       = models.CharField(max_length=200)
    slug       = models.SlugField(max_length=220, unique=True)
    kind       = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_ORGANIZATION)
    owner      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_workspaces')
    planned_image_count = models.PositiveIntegerField(default=0, help_text="Expected total number of images for this project")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-kind', 'name']  # personal first is convenient
        constraints = [
            # Each user may have at most one personal workspace.
            models.UniqueConstraint(
                fields=['owner'],
                condition=models.Q(kind='personal'),
                name='unique_personal_workspace_per_owner',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'

    @property
    def is_personal(self):
        return self.kind == self.KIND_PERSONAL

    @property
    def is_organization(self):
        return self.kind == self.KIND_ORGANIZATION

    def user_has_access(self, user):
        if not user.is_authenticated:
            return False
        if self.owner_id == user.id:
            return True
        if self.is_personal:
            return False
        return self.members.filter(user=user).exists()

    def user_is_admin(self, user):
        if self.owner_id == user.id:
            return True
        if self.is_personal:
            return False
        membership = self.members.filter(user=user).first()
        return bool(membership and membership.role == WorkspaceMember.ROLE_ADMIN)

    def get_user_role(self, user):
        if self.owner_id == user.id:
            return WorkspaceMember.ROLE_OWNER
        membership = self.members.filter(user=user).first()
        return membership.role if membership else None

    @property
    def project_count(self):
        return self.projects.filter(is_archived=False).count()

    @property
    def member_count(self):
        # Owner counts as one, plus any WorkspaceMembers.
        if self.is_personal:
            return 1
        return self.members.count() + 1

    @staticmethod
    def _unique_slug(base):
        base = slugify(base) or 'workspace'
        slug = base
        i = 2
        while Workspace.objects.filter(slug=slug).exists():
            slug = f'{base}-{i}'
            i += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug(self.name)
        super().save(*args, **kwargs)


class WorkspaceMember(models.Model):
    """Membership in an organization workspace. Not used for personal
    workspaces (the owner is the sole member)."""

    ROLE_OWNER  = 'owner'   # conceptual only — owner is Workspace.owner, not stored here
    ROLE_ADMIN  = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_ADMIN,  'Administrator'),
        (ROLE_MEMBER, 'Member'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='members')
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_memberships')
    role      = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('workspace', 'user')
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user.username} — {self.workspace.name} ({self.get_role_display()})'


class Project(models.Model):
    ANNOTATION_TYPE_CHOICES = [
        ('bbox', 'Bounding Box'),
        ('polygon', 'Polygon'),
        ('segmentation', 'Segmentation'),
        ('classification', 'Classification'),
        ('mixed', 'Mixed'),
    ]

    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    annotation_type = models.CharField(max_length=20, choices=ANNOTATION_TYPE_CHOICES, default='bbox')
    planned_image_count = models.PositiveIntegerField(default=0)
    workspace       = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='projects',
        null=True,   # temporarily nullable so the data migration can backfill
        blank=True,
    )
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
        if self.created_by_id == user.id:
            return True
        if self.members.filter(user=user).exists():
            return True
        # Only workspace admins/owners see all projects; regular members only see assigned projects.
        if self.workspace_id and self.workspace.user_is_admin(user):
            return True
        return False

    def user_is_admin(self, user):
        if self.created_by_id == user.id:
            return True
        membership = self.members.filter(user=user).first()
        if membership and membership.role == 'admin':
            return True
        # Workspace owners/admins act as project admins too.
        if self.workspace_id and self.workspace.user_is_admin(user):
            return True
        return False

    @property
    def image_count(self):
        return self.images.count()

    @property
    def completed_images(self):
        return self.images.filter(status='done').count()

    @property
    def progress_percent(self):
        if self.planned_image_count > 0:
            return round((self.completed_images / self.planned_image_count) * 100, 2)

        total = self.image_count
        if total == 0:
            return 0

        return round((self.completed_images / total) * 100, 2)

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
        # Export
        ('export_yolo',       'Exported YOLO'),
    ]

    project    = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activity_logs')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activity_logs')
    action     = models.CharField(max_length=40, choices=ACTION_CHOICES)
    detail     = models.CharField(max_length=500, blank=True)
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


class Invitation(models.Model):
    """Invitation to join a project via email."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    role = models.CharField(max_length=20, choices=ProjectMember.ROLE_CHOICES, default='annotator')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'email')
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation for {self.email} to {self.project.name}"

    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def accept(self, user):
        """Mark invitation as accepted and add the user to the project."""
        self.accepted_at = timezone.now()
        self.save()
        ProjectMember.objects.get_or_create(
            project=self.project,
            user=user,
            defaults={'role': self.role}
        )


class WorkspaceInvitation(models.Model):
    """Invitation to join a workspace via email."""
    workspace  = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invitations')
    email      = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_workspace_invitations')
    role       = models.CharField(max_length=20, choices=WorkspaceMember.ROLE_CHOICES, default=WorkspaceMember.ROLE_MEMBER)
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('workspace', 'email')
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite for {self.email} to {self.workspace.name}"

    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    def accept(self, user):
        self.accepted_at = timezone.now()
        self.save(update_fields=['accepted_at'])
        WorkspaceMember.objects.get_or_create(
            workspace=self.workspace,
            user=user,
            defaults={'role': self.role},
        )