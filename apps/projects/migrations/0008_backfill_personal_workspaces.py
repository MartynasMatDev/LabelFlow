from django.db import migrations
from django.utils.text import slugify


def _unique_slug(Workspace, base):
    base = slugify(base) or 'workspace'
    slug = base
    i = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f'{base}-{i}'
        i += 1
    return slug


def forwards(apps, schema_editor):
    """For every user who owns projects, create a personal workspace and
    attach their owned projects to it. Projects where the creator already
    has a personal workspace just reuse it."""

    User      = apps.get_model('auth', 'User')
    Project   = apps.get_model('projects', 'Project')
    Workspace = apps.get_model('projects', 'Workspace')

    # Users that need a personal workspace: owners of any existing project.
    owner_ids = Project.objects.values_list('created_by_id', flat=True).distinct()
    owners    = User.objects.filter(pk__in=list(owner_ids))

    for user in owners:
        ws = Workspace.objects.filter(owner=user, kind='personal').first()
        if not ws:
            full = f'{user.first_name} {user.last_name}'.strip()
            name = (full or user.username or 'Personal').strip()
            ws = Workspace.objects.create(
                owner=user,
                name=f"{name}'s workspace",
                kind='personal',
                slug=_unique_slug(Workspace, f'personal-{user.username}'),
                emoji='◈',
            )
        Project.objects.filter(
            created_by=user, workspace__isnull=True
        ).update(workspace=ws)


def backwards(apps, schema_editor):
    # Detach projects from workspaces, leave Workspace rows in place (they're
    # harmless and removing them risks deleting user-created data).
    Project = apps.get_model('projects', 'Project')
    Project.objects.update(workspace=None)


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_workspace_project_workspace_workspacemember_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
