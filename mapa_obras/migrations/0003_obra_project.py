# Generated manually — vínculo explícito Mapa ↔ Diário (cadastro canónico em core.Project)

from django.db import migrations, models
import django.db.models.deletion


def link_obras_to_projects(apps, schema_editor):
    Project = apps.get_model('core', 'Project')
    Obra = apps.get_model('mapa_obras', 'Obra')
    for p in Project.objects.all().iterator():
        o = Obra.objects.filter(codigo_sienge=p.code).first()
        if o and o.project_id is None:
            o.project_id = p.id
            o.save(update_fields=['project'])


def noop_reverse(apps, schema_editor):
    Obra = apps.get_model('mapa_obras', 'Obra')
    Obra.objects.all().update(project=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_project_sienge_codigos_alternativos'),
        ('mapa_obras', '0002_obra_codigos_sienge_alternativos'),
    ]

    operations = [
        migrations.AddField(
            model_name='obra',
            name='project',
            field=models.OneToOneField(
                blank=True,
                help_text='Projeto canónico do Diário de Obra. Preenchido pela sincronização ao guardar o projeto; mantém o vínculo explícito além do código Sienge.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='obra_mapa',
                to='core.project',
            ),
        ),
        migrations.RunPython(link_obras_to_projects, noop_reverse),
    ]
