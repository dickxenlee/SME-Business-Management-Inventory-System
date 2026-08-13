from django.db import migrations


def create_staff_group(apps, schema_editor):
    group = apps.get_model("auth", "Group")
    group.objects.get_or_create(name="Staff")


def remove_staff_group(apps, schema_editor):
    group = apps.get_model("auth", "Group")
    group.objects.filter(name="Staff").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_staff_group, remove_staff_group),
    ]

