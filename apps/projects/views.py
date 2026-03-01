from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    ANNOTATION_TYPE_CHOICES = [
        ('bbox', 'Bounding Box'),
        ('polygon', 'Poligonas'),
        ('classification', 'Klasifikavimas'),
        ('mixed', 'Mišrus'),
    ]

    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    annotation_type = models.CharField(max_length=20, choices=ANNOTATION_TYPE_CHOICES, default='bbox')
    emoji           = models.CharField(max_length=4, default='◈')
    created_by      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def get_user_role(self, user):
        """Returns the role of a user in this project, or None."""
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


class ProjectMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administratorius'),
        ('annotator', 'Anotatorius'),
        ('viewer', 'Peržiūrėtojas'),
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
