"""
数据层 — MyVideoPic 纯本地媒体中心.

设计要点:
  * 主键统一 UUID，缩略图以 UUID 命名，与物理文件名彻底解耦（重命名/移动后封面不丢）
  * 只记录路径，绝不复制原文件（零侵入）
  * 历史记录按 (对象, 动作) 去重，保存播放进度，支持"继续观看"
"""
import uuid

from django.db import models


class MediaLibrary(models.Model):
    """媒体库配置 — 映射一个物理文件夹."""

    class LibraryType(models.TextChoices):
        VIDEO = 'video', '视频'
        PHOTO = 'photo', '图片'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256, verbose_name='库名称')
    folder_path = models.CharField(
        max_length=2048, unique=True, verbose_name='物理文件夹绝对路径',
    )
    library_type = models.CharField(
        max_length=16, choices=LibraryType.choices,
        default=LibraryType.VIDEO, verbose_name='库类型',
    )
    category = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='分类标签（电影/剧集/动漫…，用于前端筛选）',
    )
    enabled = models.BooleanField(default=True, verbose_name='参与扫描')
    last_scanned_at = models.DateTimeField(
        null=True, blank=True, verbose_name='最后扫描时间',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'media_libraries'
        ordering = ['library_type', '-created_at']
        verbose_name = '媒体库'
        verbose_name_plural = '媒体库'

    def __str__(self):
        return f'{self.name} ({self.folder_path})'


class MediaItem(models.Model):
    """视频与图片的公共字段抽象基类（不建表）."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=512, verbose_name='显示名（不含扩展名）')
    original_filename = models.CharField(max_length=512, verbose_name='文件名（含扩展名）')
    absolute_path = models.CharField(
        max_length=2048, unique=True, verbose_name='物理绝对路径',
    )
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小 (bytes)')
    file_mtime = models.FloatField(
        default=0, verbose_name='文件修改时间戳（增量扫描判定用）',
    )
    cover_path = models.CharField(
        max_length=2048, blank=True, default='',
        verbose_name='缩略图路径（.app_data/ 内，UUID 命名）',
    )
    width = models.IntegerField(null=True, blank=True, verbose_name='宽')
    height = models.IntegerField(null=True, blank=True, verbose_name='高')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='入库时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Video(MediaItem):
    """视频媒体."""

    duration = models.FloatField(null=True, blank=True, verbose_name='时长 (秒)')
    video_codec = models.CharField(max_length=128, blank=True, default='', verbose_name='视频编码')
    audio_codec = models.CharField(max_length=128, blank=True, default='', verbose_name='音频编码')
    container_format = models.CharField(max_length=64, blank=True, default='', verbose_name='封装格式')
    browser_compatible = models.BooleanField(default=True, verbose_name='浏览器可直接播放')
    year = models.IntegerField(null=True, blank=True, verbose_name='年份（从文件名推断）')
    library = models.ForeignKey(
        MediaLibrary, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='videos', verbose_name='所属媒体库',
    )

    class Meta:
        db_table = 'videos'
        ordering = ['-created_at']
        verbose_name = '视频'
        verbose_name_plural = '视频'
        indexes = [
            models.Index(fields=['-created_at'], name='video_created_idx'),
            models.Index(fields=['name'], name='video_name_idx'),
        ]


class Photo(MediaItem):
    """图片媒体."""

    exif_orientation = models.IntegerField(
        null=True, blank=True, verbose_name='原始 EXIF 方向',
    )
    taken_at = models.DateTimeField(
        null=True, blank=True, verbose_name='拍摄时间（EXIF DateTimeOriginal）',
    )
    library = models.ForeignKey(
        MediaLibrary, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='photos', verbose_name='所属相册',
    )

    class Meta:
        db_table = 'photos'
        ordering = ['-created_at']
        verbose_name = '图片'
        verbose_name_plural = '图片'
        indexes = [
            models.Index(fields=['-created_at'], name='photo_created_idx'),
            models.Index(fields=['name'], name='photo_name_idx'),
        ]


class ContentType(models.TextChoices):
    """多态内容类型 — 收藏与历史共用."""

    VIDEO = 'video', '视频'
    PHOTO = 'photo', '图片'


class Favorite(models.Model):
    """收藏夹 — 多态关联视频或图片."""

    ContentType = ContentType

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.CharField(
        max_length=16, choices=ContentType.choices, verbose_name='类型',
    )
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, null=True, blank=True,
        related_name='favorites',
    )
    photo = models.ForeignKey(
        Photo, on_delete=models.CASCADE, null=True, blank=True,
        related_name='favorites',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')

    class Meta:
        db_table = 'favorites'
        ordering = ['-created_at']
        verbose_name = '收藏'
        verbose_name_plural = '收藏'
        constraints = [
            models.UniqueConstraint(
                fields=['video'], name='unique_video_favorite',
                condition=models.Q(video__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['photo'], name='unique_photo_favorite',
                condition=models.Q(photo__isnull=False),
            ),
        ]

    def __str__(self):
        target = self.video or self.photo
        return f'⭐ {target.name if target else "?"}'


class HistoryEntry(models.Model):
    """
    浏览/播放历史.

    同一对象同一动作只保留一条（按 last_seen_at 更新），
    避免反复播放导致历史被同一个文件刷满.
    """

    class ActionType(models.TextChoices):
        VIEW = 'view', '浏览'
        PLAY = 'play', '播放'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.CharField(
        max_length=16, choices=ContentType.choices, verbose_name='类型',
    )
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, null=True, blank=True,
        related_name='history',
    )
    photo = models.ForeignKey(
        Photo, on_delete=models.CASCADE, null=True, blank=True,
        related_name='history',
    )
    action = models.CharField(
        max_length=16, choices=ActionType.choices,
        default=ActionType.VIEW, verbose_name='操作类型',
    )
    position = models.FloatField(
        default=0, verbose_name='播放进度位置 (秒)',
    )
    percent = models.FloatField(
        default=0, verbose_name='播放百分比 0-100',
    )
    play_count = models.IntegerField(default=1, verbose_name='累计次数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='首次时间')
    last_seen_at = models.DateTimeField(auto_now=True, verbose_name='最近时间')

    class Meta:
        db_table = 'history'
        ordering = ['-last_seen_at']
        verbose_name = '历史记录'
        verbose_name_plural = '历史记录'
        constraints = [
            models.UniqueConstraint(
                fields=['video', 'action'], name='unique_video_history',
                condition=models.Q(video__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['photo', 'action'], name='unique_photo_history',
                condition=models.Q(photo__isnull=False),
            ),
        ]

    def __str__(self):
        target = self.video or self.photo
        return f'{self.get_action_display()} — {target.name if target else "?"}'


class ScanRecord(models.Model):
    """一次扫描的结果快照 — 设置页"上次扫描"面板的数据源."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField(verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    duration_seconds = models.FloatField(default=0, verbose_name='耗时 (秒)')
    total_files = models.IntegerField(default=0, verbose_name='扫描文件总数')
    added = models.IntegerField(default=0, verbose_name='新增')
    updated = models.IntegerField(default=0, verbose_name='更新')
    removed = models.IntegerField(default=0, verbose_name='清理')
    failed = models.IntegerField(default=0, verbose_name='失败')
    status = models.CharField(max_length=16, default='completed', verbose_name='结果状态')
    message = models.CharField(max_length=512, blank=True, default='', verbose_name='摘要')

    class Meta:
        db_table = 'scan_records'
        ordering = ['-started_at']
        verbose_name = '扫描记录'
        verbose_name_plural = '扫描记录'

    def __str__(self):
        return f'{self.started_at:%Y-%m-%d %H:%M} — 新增{self.added} 更新{self.updated}'


class AppSetting(models.Model):
    """
    应用偏好设置 — 键值对（值存 JSON）.

    覆盖设置页的"播放设置"与"外观"分组，纯本地存储，不出网.
    """

    key = models.CharField(max_length=64, primary_key=True, verbose_name='配置键')
    value = models.JSONField(default=dict, verbose_name='配置值')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'app_settings'
        ordering = ['key']
        verbose_name = '应用设置'
        verbose_name_plural = '应用设置'

    def __str__(self):
        return f'{self.key} = {self.value}'
