from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cine', '0016_historicalfuncion_historicalpelicula_historicalsala'),
    ]

    operations = [
        migrations.CreateModel(
            name='Genero',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'verbose_name': 'Género',
                'verbose_name_plural': 'Géneros',
                'ordering': ['nombre'],
                'db_table': 'generos',
            },
        ),
        migrations.AddField(
            model_name='pelicula',
            name='generos',
            field=models.ManyToManyField(blank=True, related_name='peliculas', to='cine.Genero'),
        ),
    ]
