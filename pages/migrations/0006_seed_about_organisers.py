from django.db import migrations


ORGANISERS = (
    {
        "name": "Dario",
        "role": "Founder",
        "bio": (
            "Dario founded JamSession Lab. He is a drummer and the driving force "
            "behind the project's vision and community."
        ),
        "initials": "D",
        "order": 0,
    },
    {
        "name": "Rita",
        "role": "Event & Logistics Coordinator",
        "bio": (
            "Rita organises the logistics of every event, manages door registrations, "
            "and helps musicians and guests understand how the sessions work."
        ),
        "initials": "R",
        "order": 1,
    },
    {
        "name": "M.D. Productions",
        "role": "Sound Engineer",
        "bio": (
            "Denis is the owner of M.D. Productions and one of the best sound engineers "
            "in the area. He provides top-quality sound equipment and supports everything "
            "happening on stage."
        ),
        "initials": "MD",
        "order": 2,
    },
)


def seed_organisers(apps, schema_editor):
    AboutOrganiser = apps.get_model("pages", "AboutOrganiser")
    if not AboutOrganiser.objects.exists():
        AboutOrganiser.objects.bulk_create(
            [AboutOrganiser(**fields, is_active=True) for fields in ORGANISERS]
        )

    # Refresh Staff group so organisers permissions are included.
    from accounts.staff_permissions import ensure_staff_group

    ensure_staff_group()


def unseed_organisers(apps, schema_editor):
    AboutOrganiser = apps.get_model("pages", "AboutOrganiser")
    AboutOrganiser.objects.filter(
        name__in=["Dario", "Rita", "Denis", "M.D. Productions"],
        photo="",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0005_aboutorganiser"),
    ]

    operations = [
        migrations.RunPython(seed_organisers, unseed_organisers),
    ]
