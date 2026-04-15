from django.db import migrations


def seed_policies(apps, schema_editor):
    Policy = apps.get_model('audit', 'AuditRetentionPolicy')
    Policy.objects.get_or_create(
        key='audit_events',
        defaults={
            'description': 'Retenção sugerida para eventos de auditoria (governança). Ajuste no Admin.',
            'retention_days': 730,
        },
    )
    Policy.objects.get_or_create(
        key='user_login_log',
        defaults={
            'description': 'Retenção sugerida para trilho de login (IP/UA). Ajuste no Admin.',
            'retention_days': 365,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_policies, migrations.RunPython.noop),
    ]
