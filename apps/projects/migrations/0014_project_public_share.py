import uuid
from django.db import migrations, models


def gen_tokens(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')
    for p in Project.objects.all():
        p.share_token = uuid.uuid4()
        p.save(update_fields=['share_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0013_alter_project_annotation_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_public',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='project',
            name='share_token',
            field=models.UUIDField(default=uuid.uuid4, null=True, editable=False),
        ),
        migrations.RunPython(gen_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='project',
            name='share_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
