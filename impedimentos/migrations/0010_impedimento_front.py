# Generated manually for ProjectFront on Impedimento

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_projectfrontmember"),
        ("impedimentos", "0009_alter_verbose_restricoes"),
    ]

    operations = [
        migrations.AddField(
            model_name="impedimento",
            name="front",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="impedimentos",
                to="core.projectfront",
                verbose_name="Frente",
            ),
        ),
        migrations.AddIndex(
            model_name="impedimento",
            index=models.Index(fields=["front"], name="impedimentos_impedimento_front_idx"),
        ),
    ]
