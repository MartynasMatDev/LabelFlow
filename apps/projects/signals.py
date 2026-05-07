from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.urls import NoReverseMatch, reverse

from .models import ActivityLog, Notification, Project, ProjectMember, Workspace, WorkspaceMember


# Activity actions that should generate notifications for teammates.
NOTIFY_ACTIONS = {
    'member_added',
    'member_removed',
    'role_changed',
    'image_uploaded',
    'image_deleted',
    'annotation_done',
    'tag_added',
    'tag_removed',
    'project_archived',
    'project_restored',
    'comment',
}


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


def _project_recipients(project, exclude_user):
    """All users who should be notified about activity in `project`,
    excluding the actor. Includes project members, project creator,
    and workspace owner/members."""
    user_ids = set()
    user_ids.update(
        ProjectMember.objects.filter(project=project).values_list('user_id', flat=True)
    )
    if project.created_by_id:
        user_ids.add(project.created_by_id)
    if project.workspace_id:
        ws = project.workspace
        if ws.is_organization:
            user_ids.add(ws.owner_id)
            user_ids.update(
                WorkspaceMember.objects.filter(workspace=ws).values_list('user_id', flat=True)
            )
    if exclude_user is not None:
        user_ids.discard(exclude_user.id)
    return user_ids


@receiver(post_save, sender=ActivityLog)
def fan_out_notifications(sender, instance, created, **kwargs):
    """When an ActivityLog row is created, notify all teammates on the
    project (excluding the actor) for actions that team members care
    about. Failures are silent — never break the main flow."""
    if not created:
        return
    if instance.action not in NOTIFY_ACTIONS:
        return
    try:
        project = instance.project
        recipient_ids = _project_recipients(project, instance.user)
        if not recipient_ids:
            return

        try:
            url = reverse('project_detail', args=[project.id])
        except NoReverseMatch:
            url = ''

        Notification.objects.bulk_create([
            Notification(
                recipient_id=uid,
                actor=instance.user,
                project=project,
                kind=instance.action,
                detail=instance.detail or project.name,
                url=url,
            )
            for uid in recipient_ids
        ])
    except (OperationalError, ProgrammingError):
        # Notification table not ready yet (mid-migration).
        pass
    except Exception:
        # Notifications must never break activity logging.
        pass
