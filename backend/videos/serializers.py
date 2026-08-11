"""
序列化层.

注意 absolute_path 仍然对外返回 —— 前端"复制路径"会使用它；默认播放器接口也会
在后端使用它。这是本地单用户应用，不存在跨用户泄露问题。
"""
import os

from rest_framework import serializers

from .models import (
    Favorite, HistoryEntry, MediaLibrary, Photo, ScanRecord, Video,
)


def resolution_label(width, height) -> str:
    """按短边归档成 4K / 1080P / 720P 之类的角标文案."""
    if not width or not height:
        return ''
    short = min(width, height)
    if short >= 2000:
        return '4K'
    if short >= 1400:
        return '2K'
    if short >= 1000:
        return '1080P'
    if short >= 700:
        return '720P'
    if short >= 500:
        return '576P'
    return f'{short}P'


class MediaLibrarySerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    path_exists = serializers.SerializerMethodField()

    class Meta:
        model = MediaLibrary
        fields = ['id', 'name', 'folder_path', 'library_type', 'category',
                  'enabled', 'last_scanned_at', 'created_at',
                  'item_count', 'path_exists']
        read_only_fields = ['id', 'created_at', 'last_scanned_at',
                            'item_count', 'path_exists']

    def get_item_count(self, obj):
        """按库类型返回对应的条目数（图片库不该显示视频数）."""
        if obj.library_type == MediaLibrary.LibraryType.PHOTO:
            return getattr(obj, 'photo_total', None) or obj.photos.count()
        return getattr(obj, 'video_total', None) or obj.videos.count()

    def get_path_exists(self, obj):
        return os.path.isdir(obj.folder_path) if obj.folder_path else False

    def validate_folder_path(self, value):
        value = (value or '').strip().strip('"').rstrip('\\/')
        if not value:
            raise serializers.ValidationError('请填写文件夹路径')
        if not os.path.isabs(value):
            raise serializers.ValidationError('请填写绝对路径，例如 D:\\Movies')
        if not os.path.exists(value):
            raise serializers.ValidationError('该路径不存在，请检查磁盘是否已连接')
        if not os.path.isdir(value):
            raise serializers.ValidationError('该路径是文件而不是文件夹')
        return value

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('请填写库名称')
        return value


class VideoSerializer(serializers.ModelSerializer):
    library_name = serializers.CharField(source='library.name', default='', read_only=True)
    library_category = serializers.CharField(source='library.category', default='', read_only=True)
    is_favorited = serializers.SerializerMethodField()
    resolution_label = serializers.SerializerMethodField()
    play_position = serializers.SerializerMethodField()
    play_percent = serializers.SerializerMethodField()
    file_exists = serializers.SerializerMethodField()
    has_cover = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            'id', 'name', 'original_filename', 'absolute_path',
            'file_size', 'duration', 'width', 'height', 'year',
            'video_codec', 'audio_codec', 'container_format',
            'browser_compatible', 'library_id', 'library_name',
            'library_category', 'created_at', 'is_favorited',
            'resolution_label', 'play_position', 'play_percent',
            'file_exists', 'has_cover',
        ]
        read_only_fields = fields

    def get_is_favorited(self, obj):
        cache = self.context.get('favorited_ids')
        if cache is not None:
            return obj.id in cache
        return Favorite.objects.filter(video=obj).exists()

    def get_resolution_label(self, obj):
        return resolution_label(obj.width, obj.height)

    def get_play_position(self, obj):
        cache = self.context.get('progress_map')
        if cache is not None:
            return cache.get(obj.id, (0, 0))[0]
        entry = obj.history.filter(action='play').first()
        return entry.position if entry else 0

    def get_play_percent(self, obj):
        cache = self.context.get('progress_map')
        if cache is not None:
            return cache.get(obj.id, (0, 0))[1]
        entry = obj.history.filter(action='play').first()
        return entry.percent if entry else 0

    def get_file_exists(self, obj):
        """
        仅在明确请求时才做磁盘检查.

        列表页有几百条记录，逐个 os.path.isfile 会让接口变慢，
        因此默认不检查，详情/播放页再按需传入 check_files=True.
        """
        if not self.context.get('check_files'):
            return None
        return os.path.isfile(obj.absolute_path)

    def get_has_cover(self, obj):
        """封面本身走 /api/cover/video/<id>/ 取，这里只告诉前端有没有."""
        return bool(obj.cover_path)


class PhotoSerializer(serializers.ModelSerializer):
    library_name = serializers.CharField(source='library.name', default='', read_only=True)
    library_category = serializers.CharField(source='library.category', default='', read_only=True)
    is_favorited = serializers.SerializerMethodField()
    resolution_label = serializers.SerializerMethodField()
    has_cover = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            'id', 'name', 'original_filename', 'absolute_path',
            'file_size', 'width', 'height', 'exif_orientation', 'taken_at',
            'library_id', 'library_name', 'library_category',
            'created_at', 'is_favorited', 'resolution_label', 'has_cover',
        ]
        read_only_fields = fields

    def get_is_favorited(self, obj):
        cache = self.context.get('favorited_ids')
        if cache is not None:
            return obj.id in cache
        return Favorite.objects.filter(photo=obj).exists()

    def get_resolution_label(self, obj):
        if obj.width and obj.height:
            return f'{obj.width}×{obj.height}'
        return ''

    def get_has_cover(self, obj):
        return bool(obj.cover_path)


class FavoriteSerializer(serializers.ModelSerializer):
    video = VideoSerializer(read_only=True)
    photo = PhotoSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'content_type', 'video', 'photo', 'created_at']
        read_only_fields = fields


class HistorySerializer(serializers.ModelSerializer):
    video = VideoSerializer(read_only=True)
    photo = PhotoSerializer(read_only=True)

    class Meta:
        model = HistoryEntry
        fields = ['id', 'content_type', 'action', 'position', 'percent',
                  'play_count', 'video', 'photo', 'created_at', 'last_seen_at']
        read_only_fields = fields


class ScanRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanRecord
        fields = ['id', 'started_at', 'finished_at', 'duration_seconds',
                  'total_files', 'added', 'updated', 'removed', 'failed',
                  'status', 'message']
        read_only_fields = fields


# AppSetting 走的是 key/value 扁平字典接口（见 views.app_settings），
# 不需要 ModelSerializer。
