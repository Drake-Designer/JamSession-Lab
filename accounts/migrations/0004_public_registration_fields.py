# Hand-written migration for the public registration system.
#
# Written manually (instead of auto-generated) because it needs data
# migrations between schema steps:
#   1. populate display_name from the existing username (must be unique),
#   2. convert the old single "instrument" value into the new
#      "instruments" JSON list,
#   3. give every existing row its own email verification token
#      (a column default would give all rows the same UUID).
#
# Choice lists are imported from accounts.constants so the migration always
# matches the model definition exactly.

import uuid

from django.db import migrations, models

import accounts.validators
from accounts.constants import County, MusicGenre


def populate_registration_fields(apps, schema_editor):
    User = apps.get_model("accounts", "User")

    used_display_names = set()
    for user in User.objects.order_by("pk"):
        base = (user.username or f"user{user.pk}")[:20]
        candidate = base
        counter = 2
        while candidate.lower() in used_display_names:
            suffix = str(counter)
            candidate = base[: 20 - len(suffix)] + suffix
            counter += 1
        used_display_names.add(candidate.lower())

        user.display_name = candidate
        if user.instrument:
            user.instruments = [user.instrument]
        user.instrument_other = (user.instrument_other or "")[:15]
        user.email_verification_token = uuid.uuid4()
        user.save(
            update_fields=[
                "display_name",
                "instruments",
                "instrument_other",
                "email_verification_token",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_profile_picture"),
    ]

    operations = [
        # First and last name become required (form-level, blank=False).
        migrations.AlterField(
            model_name="user",
            name="first_name",
            field=models.CharField(max_length=150, verbose_name="first name"),
        ),
        migrations.AlterField(
            model_name="user",
            name="last_name",
            field=models.CharField(max_length=150, verbose_name="last name"),
        ),
        # Email becomes unique across the system.
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                max_length=254, unique=True, verbose_name="email address"
            ),
        ),
        # New fields. display_name starts nullable so existing rows can be
        # populated before the unique constraint is applied below.
        migrations.AddField(
            model_name="user",
            name="display_name",
            field=models.CharField(
                help_text="Public nickname, maximum 20 characters including spaces.",
                max_length=20,
                null=True,
                verbose_name="display name",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_number",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Used to send you an automatic invitation to the community "
                    "WhatsApp group."
                ),
                max_length=20,
                validators=[accounts.validators.phone_number_validator],
                verbose_name="phone number",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="county",
            field=models.CharField(
                blank=True,
                choices=County.choices,
                max_length=20,
                verbose_name="county",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="town_city",
            field=models.CharField(
                blank=True, max_length=60, verbose_name="town / city"
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="instruments",
            field=models.JSONField(
                blank=True, default=list, verbose_name="instruments played"
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_email_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verification_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AddField(
            model_name="user",
            name="terms_accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Populate the new fields for any existing users.
        migrations.RunPython(
            populate_registration_fields,
            migrations.RunPython.noop,
        ),
        # Now that every row has a value, enforce unique + non-null.
        migrations.AlterField(
            model_name="user",
            name="display_name",
            field=models.CharField(
                help_text="Public nickname, maximum 20 characters including spaces.",
                max_length=20,
                unique=True,
                verbose_name="display name",
            ),
        ),
        # The single-choice instrument field is replaced by the JSON list.
        migrations.RemoveField(
            model_name="user",
            name="instrument",
        ),
        migrations.RenameField(
            model_name="user",
            old_name="instrument_other",
            new_name="other_instrument",
        ),
        migrations.AlterField(
            model_name="user",
            name="other_instrument",
            field=models.CharField(
                blank=True,
                help_text="Specify your instrument if you selected 'Other'.",
                max_length=15,
                verbose_name="other instrument",
            ),
        ),
        migrations.RenameField(
            model_name="user",
            old_name="favourite_genre",
            new_name="preferred_genre",
        ),
        migrations.AlterField(
            model_name="user",
            name="preferred_genre",
            field=models.CharField(
                blank=True,
                choices=MusicGenre.choices,
                max_length=30,
                verbose_name="preferred music genre",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="bio",
            field=models.TextField(blank=True, verbose_name="bio"),
        ),
    ]
