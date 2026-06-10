from django.db import migrations

from recursos_humanos.fix_ricardo_docs import fix_ricardo_docs, unfix_ricardo_docs


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0002_seed_mvp_data'),
    ]

    operations = [
        migrations.RunPython(fix_ricardo_docs, unfix_ricardo_docs),
    ]
