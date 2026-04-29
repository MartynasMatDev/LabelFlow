from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Workspace


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_personal_workspace(sender, instance, created, **kwargs):
    """Every new user gets a personal workspace.

    Swallows DB errors that can occur if a User is saved before
    the projects_workspace table exists (e.g. during a partial
    migration). The workspace will be lazily created on first access
    via ``get_personal_workspace`` in that case."""
    if not created:
        return
    try:
        if Workspace.objects.filter(owner=instance, kind=Workspace.KIND_PERSONAL).exists():
            return
        name = (instance.get_full_name() or instance.username or 'Personal').strip()
        Workspace.objects.create(
            owner=instance,
            name=f"{name}'s workspace",
            kind=Workspace.KIND_PERSONAL,
        )
    except (OperationalError, ProgrammingError):
        # Workspace table isn't ready yet — recoverable lazily later.
        pass
