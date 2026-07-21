from django.db import migrations

NEW_NAME = "M.D. Productions"
NEW_BIO = (
    "Denis is the owner of M.D. Productions and one of the best sound engineers "
    "in the area. He provides top-quality sound equipment and supports everything "
    "happening on stage."
)
NEW_INITIALS = "MD"

OLD_NAME = "Denis"
OLD_BIO = (
    "Denis provides all the top-quality sound equipment and supports everything "
    "happening on stage. Without him, we'd be lost."
)
OLD_INITIALS = "De"


def forwards(apps, schema_editor):
    AboutOrganiser = apps.get_model("pages", "AboutOrganiser")
    AboutOrganiser.objects.filter(name=OLD_NAME).update(
        name=NEW_NAME,
        bio=NEW_BIO,
        initials=NEW_INITIALS,
    )


def backwards(apps, schema_editor):
    AboutOrganiser = apps.get_model("pages", "AboutOrganiser")
    AboutOrganiser.objects.filter(name=NEW_NAME).update(
        name=OLD_NAME,
        bio=OLD_BIO,
        initials=OLD_INITIALS,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0007_aboutorganiser_photo_focus"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
