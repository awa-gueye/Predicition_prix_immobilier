# Generated migration for ImmoPredict SN updates
# SearchHistory, Alert models + UserProfile location fields

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('listings', '0001_initial'),
    ]

    operations = [
        # Add location fields to UserProfile
        migrations.AddField(
            model_name='userprofile',
            name='latitude',
            field=models.FloatField(blank=True, help_text="Latitude de l'utilisateur pour les alertes de proximite", null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='longitude',
            field=models.FloatField(blank=True, help_text="Longitude de l'utilisateur pour les alertes de proximite", null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='alert_radius_km',
            field=models.FloatField(default=5.0, help_text='Rayon d alerte en km'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='alerts_enabled',
            field=models.BooleanField(default=True, help_text='Recevoir des alertes de proximite'),
        ),
        # SearchHistory model
        migrations.CreateModel(
            name='SearchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city', models.CharField(blank=True, max_length=100)),
                ('property_type', models.CharField(blank=True, max_length=50)),
                ('transaction', models.CharField(blank=True, max_length=10)),
                ('query_text', models.CharField(blank=True, max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='search_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Historique de recherche',
                'verbose_name_plural': 'Historiques de recherche',
                'ordering': ['-created_at'],
            },
        ),
        # Alert model
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('proximity', 'Bien a proximite'), ('price_drop', 'Baisse de prix'), ('new_listing', 'Nouvelle annonce'), ('recommendation', 'Recommandation')], default='proximity', max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('property_title', models.CharField(blank=True, max_length=200)),
                ('property_price', models.BigIntegerField(blank=True, null=True)),
                ('property_city', models.CharField(blank=True, max_length=100)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alerts', to='listings.listing')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Alerte',
                'verbose_name_plural': 'Alertes',
                'ordering': ['-created_at'],
            },
        ),
    ]
