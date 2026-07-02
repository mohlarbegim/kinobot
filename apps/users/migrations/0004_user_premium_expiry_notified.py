from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_premium_first_view'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='premium_expiry_notified',
            field=models.BooleanField(default=False, verbose_name='Tugash eslatmasi yuborilgan'),
        ),
    ]
