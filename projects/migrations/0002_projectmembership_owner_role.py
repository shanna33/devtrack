from django.db import migrations, models


def mark_project_owners(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    ProjectMembership = apps.get_model("projects", "ProjectMembership")
    database = schema_editor.connection.alias
    for project_id, owner_id in Project.objects.using(database).values_list("pk", "owner_id").iterator():
        ProjectMembership.objects.using(database).filter(
            project_id=project_id,
            user_id=owner_id,
        ).update(role="owner")


def restore_manager_role(apps, schema_editor):
    ProjectMembership = apps.get_model("projects", "ProjectMembership")
    ProjectMembership.objects.using(schema_editor.connection.alias).filter(role="owner").update(role="manager")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectmembership",
            name="role",
            field=models.CharField(
                choices=[("owner", "Owner"), ("manager", "Manager"), ("member", "Member")],
                default="member",
                max_length=20,
            ),
        ),
        migrations.RunPython(mark_project_owners, restore_manager_role),
    ]
