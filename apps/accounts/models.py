from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True)
    organization = models.CharField(max_length=200, blank=True)
    job_title = models.CharField(max_length=200, blank=True)
    # Notification prefs
    notify_team_invites = models.BooleanField(default=True)
    notify_comments = models.BooleanField(default=True)
    notify_weekly = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile({self.user.username})"

    def get_initials(self):
        first = self.user.first_name[:1].upper() if self.user.first_name else ''
        last = self.user.last_name[:1].upper() if self.user.last_name else ''
        return (first + last) or self.user.username[:2].upper()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
