from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_seed_tipos_comunicacao_complementares'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='preferenciacomunicacao',
            name='core_prefcom_unique_tipo_usuario',
        ),
        migrations.RemoveConstraint(
            model_name='preferenciacomunicacao',
            name='core_prefcom_unique_tipo_email',
        ),
    ]
