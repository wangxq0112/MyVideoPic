"""API 路由表 — 全部挂在 /api/ 之下."""
from django.urls import path

from . import views

urlpatterns = [
    # ── 视频 ──────────────────────────────────────────
    path('videos/', views.VideoListView.as_view(), name='video-list'),
    path('videos/<uuid:video_id>/', views.VideoDetailView.as_view(), name='video-detail'),
    path('videos/<uuid:video_id>/rename/', views.video_rename, name='video-rename'),
    path('videos/<uuid:video_id>/move/', views.video_move, name='video-move'),
    path('videos/<uuid:video_id>/delete/', views.video_delete, name='video-delete'),
    path('videos/<uuid:video_id>/progress/', views.update_progress, name='video-progress'),

    # ── 图片 ──────────────────────────────────────────
    path('photos/', views.PhotoListView.as_view(), name='photo-list'),
    path('photos/<uuid:photo_id>/rename/', views.photo_rename, name='photo-rename'),
    path('photos/<uuid:photo_id>/move/', views.photo_move, name='photo-move'),
    path('photos/<uuid:photo_id>/delete/', views.photo_delete, name='photo-delete'),

    # ── 缩略图 / 原始媒体流（支持 206 Range）──────────
    path('thumbnails/video/<uuid:video_id>/', views.serve_video_thumbnail, name='video-thumb'),
    path('thumbnails/photo/<uuid:photo_id>/', views.serve_photo_thumbnail, name='photo-thumb'),
    path('stream/video/<uuid:video_id>/', views.stream_video, name='video-stream'),
    path('original/photo/<uuid:photo_id>/', views.serve_photo_original, name='photo-original'),

    # ── 媒体库 CRUD ───────────────────────────────────
    path('libraries/',
         views.MediaLibraryViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='library-list'),
    path('libraries/<uuid:pk>/',
         views.MediaLibraryViewSet.as_view({
             'get': 'retrieve', 'put': 'update',
             'patch': 'partial_update', 'delete': 'destroy',
         }), name='library-detail'),

    # ── 扫描（纯手动）─────────────────────────────────
    path('scan/', views.trigger_scan, name='scan-trigger'),
    path('scan/status/', views.scan_status, name='scan-status'),
    path('scan-progress/<str:task_id>/', views.scan_progress, name='scan-progress'),
    path('scan-cancel/<str:task_id>/', views.cancel_scan, name='scan-cancel'),
    path('move-progress/<str:task_id>/', views.move_progress, name='move-progress'),

    # ── 收藏 ──────────────────────────────────────────
    path('favorites/', views.FavoriteListView.as_view(), name='favorite-list'),
    path('favorites/toggle/', views.toggle_favorite, name='favorite-toggle'),

    # ── 历史 ──────────────────────────────────────────
    path('history/', views.HistoryListView.as_view(), name='history-list'),
    path('history/record/', views.record_history, name='history-record'),
    path('history/clear/', views.clear_history, name='history-clear'),
    path('history/<uuid:entry_id>/', views.delete_history_entry, name='history-delete'),

    # ── 搜索 ──────────────────────────────────────────
    path('search/', views.search, name='search'),

    # ── 统计 / 维护 / 设置 ────────────────────────────
    path('stats/', views.stats, name='stats'),
    path('settings/', views.app_settings, name='app-settings'),
    path('maintenance/clear-cache/', views.clear_thumbnail_cache, name='clear-cache'),
    path('maintenance/cleanup-orphans/', views.cleanup_orphans, name='cleanup-orphans'),
    path('browse/', views.browse_directory, name='browse'),
]
