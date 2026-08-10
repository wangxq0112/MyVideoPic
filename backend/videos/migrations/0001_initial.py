"""初始迁移 — 手写以便直接 `python manage.py migrate`，无需 makemigrations."""
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AppSetting',
            fields=[
                ('key', models.CharField(max_length=64, primary_key=True, serialize=False, verbose_name='配置键')),
                ('value', models.JSONField(default=dict, verbose_name='配置值')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '应用设置',
                'verbose_name_plural': '应用设置',
                'db_table': 'app_settings',
                'ordering': ['key'],
            },
        ),
        migrations.CreateModel(
            name='MediaLibrary',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=256, verbose_name='库名称')),
                ('folder_path', models.CharField(max_length=2048, unique=True, verbose_name='物理文件夹绝对路径')),
                ('library_type', models.CharField(choices=[('video', '视频'), ('photo', '图片')], default='video', max_length=16, verbose_name='库类型')),
                ('category', models.CharField(blank=True, default='', max_length=64, verbose_name='分类标签（电影/剧集/动漫…，用于前端筛选）')),
                ('enabled', models.BooleanField(default=True, verbose_name='参与扫描')),
                ('last_scanned_at', models.DateTimeField(blank=True, null=True, verbose_name='最后扫描时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '媒体库',
                'verbose_name_plural': '媒体库',
                'db_table': 'media_libraries',
                'ordering': ['library_type', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ScanRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('started_at', models.DateTimeField(verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('duration_seconds', models.FloatField(default=0, verbose_name='耗时 (秒)')),
                ('total_files', models.IntegerField(default=0, verbose_name='扫描文件总数')),
                ('added', models.IntegerField(default=0, verbose_name='新增')),
                ('updated', models.IntegerField(default=0, verbose_name='更新')),
                ('removed', models.IntegerField(default=0, verbose_name='清理')),
                ('failed', models.IntegerField(default=0, verbose_name='失败')),
                ('status', models.CharField(default='completed', max_length=16, verbose_name='结果状态')),
                ('message', models.CharField(blank=True, default='', max_length=512, verbose_name='摘要')),
            ],
            options={
                'verbose_name': '扫描记录',
                'verbose_name_plural': '扫描记录',
                'db_table': 'scan_records',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='Photo',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=512, verbose_name='显示名（不含扩展名）')),
                ('original_filename', models.CharField(max_length=512, verbose_name='文件名（含扩展名）')),
                ('absolute_path', models.CharField(max_length=2048, unique=True, verbose_name='物理绝对路径')),
                ('file_size', models.BigIntegerField(default=0, verbose_name='文件大小 (bytes)')),
                ('file_mtime', models.FloatField(default=0, verbose_name='文件修改时间戳（增量扫描判定用）')),
                ('cover_path', models.CharField(blank=True, default='', max_length=2048, verbose_name='缩略图路径（.app_data/ 内，UUID 命名）')),
                ('width', models.IntegerField(blank=True, null=True, verbose_name='宽')),
                ('height', models.IntegerField(blank=True, null=True, verbose_name='高')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='入库时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('exif_orientation', models.IntegerField(blank=True, null=True, verbose_name='原始 EXIF 方向')),
                ('taken_at', models.DateTimeField(blank=True, null=True, verbose_name='拍摄时间（EXIF DateTimeOriginal）')),
                ('library', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='photos', to='videos.medialibrary', verbose_name='所属相册')),
            ],
            options={
                'verbose_name': '图片',
                'verbose_name_plural': '图片',
                'db_table': 'photos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=512, verbose_name='显示名（不含扩展名）')),
                ('original_filename', models.CharField(max_length=512, verbose_name='文件名（含扩展名）')),
                ('absolute_path', models.CharField(max_length=2048, unique=True, verbose_name='物理绝对路径')),
                ('file_size', models.BigIntegerField(default=0, verbose_name='文件大小 (bytes)')),
                ('file_mtime', models.FloatField(default=0, verbose_name='文件修改时间戳（增量扫描判定用）')),
                ('cover_path', models.CharField(blank=True, default='', max_length=2048, verbose_name='缩略图路径（.app_data/ 内，UUID 命名）')),
                ('width', models.IntegerField(blank=True, null=True, verbose_name='宽')),
                ('height', models.IntegerField(blank=True, null=True, verbose_name='高')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='入库时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('duration', models.FloatField(blank=True, null=True, verbose_name='时长 (秒)')),
                ('video_codec', models.CharField(blank=True, default='', max_length=128, verbose_name='视频编码')),
                ('audio_codec', models.CharField(blank=True, default='', max_length=128, verbose_name='音频编码')),
                ('container_format', models.CharField(blank=True, default='', max_length=64, verbose_name='封装格式')),
                ('browser_compatible', models.BooleanField(default=True, verbose_name='浏览器可直接播放')),
                ('year', models.IntegerField(blank=True, null=True, verbose_name='年份（从文件名推断）')),
                ('library', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='videos', to='videos.medialibrary', verbose_name='所属媒体库')),
            ],
            options={
                'verbose_name': '视频',
                'verbose_name_plural': '视频',
                'db_table': 'videos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HistoryEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content_type', models.CharField(choices=[('video', '视频'), ('photo', '图片')], max_length=16, verbose_name='类型')),
                ('action', models.CharField(choices=[('view', '浏览'), ('play', '播放')], default='view', max_length=16, verbose_name='操作类型')),
                ('position', models.FloatField(default=0, verbose_name='播放进度位置 (秒)')),
                ('percent', models.FloatField(default=0, verbose_name='播放百分比 0-100')),
                ('play_count', models.IntegerField(default=1, verbose_name='累计次数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='首次时间')),
                ('last_seen_at', models.DateTimeField(auto_now=True, verbose_name='最近时间')),
                ('photo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='history', to='videos.photo')),
                ('video', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='history', to='videos.video')),
            ],
            options={
                'verbose_name': '历史记录',
                'verbose_name_plural': '历史记录',
                'db_table': 'history',
                'ordering': ['-last_seen_at'],
            },
        ),
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content_type', models.CharField(choices=[('video', '视频'), ('photo', '图片')], max_length=16, verbose_name='类型')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')),
                ('photo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='videos.photo')),
                ('video', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='videos.video')),
            ],
            options={
                'verbose_name': '收藏',
                'verbose_name_plural': '收藏',
                'db_table': 'favorites',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='photo',
            index=models.Index(fields=['-created_at'], name='photo_created_idx'),
        ),
        migrations.AddIndex(
            model_name='photo',
            index=models.Index(fields=['name'], name='photo_name_idx'),
        ),
        migrations.AddIndex(
            model_name='video',
            index=models.Index(fields=['-created_at'], name='video_created_idx'),
        ),
        migrations.AddIndex(
            model_name='video',
            index=models.Index(fields=['name'], name='video_name_idx'),
        ),
        migrations.AddConstraint(
            model_name='historyentry',
            constraint=models.UniqueConstraint(
                condition=models.Q(('video__isnull', False)),
                fields=('video', 'action'), name='unique_video_history'),
        ),
        migrations.AddConstraint(
            model_name='historyentry',
            constraint=models.UniqueConstraint(
                condition=models.Q(('photo__isnull', False)),
                fields=('photo', 'action'), name='unique_photo_history'),
        ),
        migrations.AddConstraint(
            model_name='favorite',
            constraint=models.UniqueConstraint(
                condition=models.Q(('video__isnull', False)),
                fields=('video',), name='unique_video_favorite'),
        ),
        migrations.AddConstraint(
            model_name='favorite',
            constraint=models.UniqueConstraint(
                condition=models.Q(('photo__isnull', False)),
                fields=('photo',), name='unique_photo_favorite'),
        ),
    ]
