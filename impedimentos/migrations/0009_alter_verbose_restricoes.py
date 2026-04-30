from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("impedimentos", "0008_impedimento_ultima_conclusao_em"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="categoriaimpedimento",
            options={
                "ordering": ["nome"],
                "verbose_name": "Categoria de restrição",
                "verbose_name_plural": "Categorias de restrições",
                "unique_together": {("obra", "nome")},
            },
        ),
        migrations.AlterField(
            model_name="impedimento",
            name="ultima_conclusao_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Data/hora da última vez que a restrição entrou no status de conclusão da obra.",
                null=True,
            ),
        ),
    ]
