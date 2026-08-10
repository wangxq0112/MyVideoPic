"""Django Admin — 应急查看/排障入口，日常操作走前端界面."""
from django.contrib import admin

from .models import (
    AppSetting, Favorite, HistoryEntry, MediaLibrary,
    Photo, ScanRecord, Video,
)


@admin.register(MediaLibrary)
class MediaLibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'library_type', 'category', 'folder_path',
                    'enabled', 'last_scanned_at')
    list_filter = ('library_type', 'enabled')
    search_fields = ('name', 'folder_path')


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('name', 'library', 'year', 'duration',
                    'browser_compatible', 'file_size', 'created_at')
    list_filter = ('browser_compatible', 'container_format', 'library')
    search_fields = ('name', 'absolute_path')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('name', 'library', 'width', 'height',
                    'exif_orientation', 'taken_at', 'created_at')
    list_filter = ('library',)
    search_fields = ('name', 'absolute_path')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'content_type', 'created_at')
    list_filter = ('content_type',)


@admin.register(HistoryEntry)
class HistoryEntryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'action', 'percent', 'play_count', 'last_seen_at')
    list_filter = ('action', 'content_type')


@admin.register(ScanRecord)
class ScanRecordAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'status', 'total_files',
                    'added', 'updated', 'removed', 'failed', 'duration_seconds')
    list_filter = ('status',)


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'updated_at')
