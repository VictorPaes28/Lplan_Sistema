from django.db import migrations

from recursos_humanos.seed_mvp_data import seed_rh_demo, unseed_rh_demo


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_rh_demo, unseed_rh_demo),
    ]
