# Generated manually for the native folder import workflow.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='medialibrary',
            name='folder_path',
            field=models.CharField(max_length=2048, verbose_name='物理文件夹绝对路径'),
        ),
        migrations.AddConstraint(
            model_name='medialibrary',
            constraint=models.UniqueConstraint(
                fields=('folder_path', 'library_type'),
                name='unique_library_path_and_type',
            ),
        ),
    ]
