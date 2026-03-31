from django.db import migrations
from django.utils.text import slugify


def seed_categories(apps, schema_editor):
    Category = apps.get_model('store', 'Category')
    names = [
        'Phone Cases',
        'Chargers',
        'USB Cables',
        'Earphones',
        'Power Banks',
        'Screen Protectors',
        'Bluetooth Speakers',
        'Mobile Stands',
    ]
    for name in names:
        Category.objects.get_or_create(
            slug=slugify(name),
            defaults={'name': name, 'description': f'{name} collection'},
        )


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('store', 'Category')
    slugs = [
        'phone-cases',
        'chargers',
        'usb-cables',
        'earphones',
        'power-banks',
        'screen-protectors',
        'bluetooth-speakers',
        'mobile-stands',
    ]
    Category.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
