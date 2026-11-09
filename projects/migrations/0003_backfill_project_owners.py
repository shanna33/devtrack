from django.db import migrations


def ensure_owner_memberships(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    ProjectMembership = apps.get_model("projects", "ProjectMembership")
    database = schema_editor.connection.alias
    memberships = ProjectMembership.objects.using(database)

    for project_id, owner_id in (
        Project.objects.using(database).values_list("pk", "owner_id").iterator()
    ):
        memberships.update_or_create(
            project_id=project_id,
            user_id=owner_id,
            defaults={"role": "owner"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_projectmembership_owner_role"),
    ]

    operations = [
        migrations.RunPython(ensure_owner_memberships, migrations.RunPython.noop),
    ]
