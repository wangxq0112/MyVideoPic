"""
接口层.

全部接口均为本地调用，不做鉴权（单用户离线应用）。
列表接口统一按"分页后再批量补充收藏/进度"的方式组装，避免 N+1 查询。
"""
import os
import shutil
import string
import subprocess
import threading

from django.conf import settings as dj_settings
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.utils import timezone
from rest_framework import generics, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .file_ops import (
    delete_file, get_move_progress, move_file, rename_file,
)
from .models import (
    AppSetting, ContentType, Favorite, HistoryEntry,
    MediaLibrary, Photo, ScanRecord, Video,
)
from .scanner import (
    PHOTO_EXTENSIONS, SKIP_DIR_NAMES, VIDEO_EXTENSIONS, ffmpeg_available,
    get_active_scan, get_scan_progress, request_cancel, start_scan,
)
from .serializers import (
    FavoriteSerializer, HistorySerializer, MediaLibrarySerializer,
    PhotoSerializer, ScanRecordSerializer, VideoSerializer,
)
from .streaming import serve_media_file

ORDERING_MAP = {
    'recent': '-created_at',
    'name': 'name',
    'name_desc': '-name',
    'size': '-file_size',
    'size_asc': 'file_size',
    'duration': '-duration',
    'duration_asc': 'duration',
    'year': '-year',
    'oldest': 'created_at',
    'taken': '-taken_at',
}


def _bad(msg, code=400):
    return Response({'error': msg}, status=code)


_folder_dialog_lock = threading.Lock()


def _choose_folder_with_system_dialog() -> tuple[str | None, str | None]:
    """打开 Windows 原生选目录窗口，返回 (路径, 错误信息)."""
    if os.name != 'nt':
        return None, '系统文件夹选择仅支持 Windows 本机环境'
    powershell = shutil.which('powershell.exe') or shutil.which('powershell')
    if not powershell:
        return None, '未找到 Windows PowerShell，无法打开系统文件夹选择器'

    script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择要添加的媒体文件夹'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::Write($dialog.SelectedPath)
}
'''
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        result = subprocess.run(
            [powershell, '-NoProfile', '-STA', '-Command', script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            creationflags=flags,
        )
    except OSError:
        return None, '无法启动系统文件夹选择器'
    if result.returncode != 0:
        return None, '系统文件夹选择器启动失败'
    raw_path = result.stdout.strip().lstrip('\ufeff')
    selected = os.path.normpath(raw_path) if raw_path else ''
    return (selected or None), None


def _detect_library_types(folder_path: str) -> dict[str, int]:
    """只读遍历一次，统计选中目录内的视频和图片文件数。"""
    counts = {'video': 0, 'photo': 0}
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [name for name in dirs
                   if name not in SKIP_DIR_NAMES and not name.startswith('.')]
        for filename in files:
            if filename.startswith('.'):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                counts['video'] += 1
            elif ext in PHOTO_EXTENSIONS:
                counts['photo'] += 1
    return counts


class MediaListMixin:
    """
    分页后再批量注入收藏标记与播放进度.

    旧实现在 get_queryset 里遍历整个 queryset 打标记，等于把分页作废
    并触发全表加载；这里改为只针对当前页的 id 做两次聚合查询。
    """

    content_type = ContentType.VIDEO

    def _build_context(self, page_objects):
        ctx = {'request': self.request}
        ids = [o.id for o in page_objects]
        if not ids:
            ctx['favorited_ids'] = set()
            ctx['progress_map'] = {}
            return ctx

        if self.content_type == ContentType.VIDEO:
            ctx['favorited_ids'] = set(
                Favorite.objects.filter(video_id__in=ids)
                .values_list('video_id', flat=True))
            ctx['progress_map'] = {
                h.video_id: (h.position, h.percent)
                for h in HistoryEntry.objects.filter(
                    video_id__in=ids, action=HistoryEntry.ActionType.PLAY)
            }
        else:
            ctx['favorited_ids'] = set(
                Favorite.objects.filter(photo_id__in=ids)
                .values_list('photo_id', flat=True))
            ctx['progress_map'] = {}
        return ctx

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer_class()(
                page, many=True, context=self._build_context(page))
            return self.get_paginated_response(serializer.data)
        objects = list(queryset)
        serializer = self.get_serializer_class()(
            objects, many=True, context=self._build_context(objects))
        return Response(serializer.data)


class NestedListMixin:
    """
    收藏 / 历史列表：每行内嵌一个 Video 或 Photo.

    内嵌序列化器会继承外层 context，所以同样只需针对当前页的
    video_id / photo_id 做两次聚合查询，避免每行各查一次。
    """

    def _build_context(self, rows):
        video_ids = [r.video_id for r in rows if r.video_id]
        photo_ids = [r.photo_id for r in rows if r.photo_id]
        favorited = set(
            Favorite.objects.filter(video_id__in=video_ids)
            .values_list('video_id', flat=True))
        favorited |= set(
            Favorite.objects.filter(photo_id__in=photo_ids)
            .values_list('photo_id', flat=True))
        progress = {
            h.video_id: (h.position, h.percent)
            for h in HistoryEntry.objects.filter(
                video_id__in=video_ids, action=HistoryEntry.ActionType.PLAY)
        }
        return {
            'request': self.request,
            'favorited_ids': favorited,
            'progress_map': progress,
        }

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        rows = page if page is not None else list(queryset)
        serializer = self.get_serializer_class()(
            rows, many=True, context=self._build_context(rows))
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


def _apply_common_filters(qs, params, *, is_video: bool):
    """库 / 分类 / 收藏 / 关键词 / 排序，五个筛选维度."""
    library_id = params.get('library')
    if library_id:
        qs = qs.filter(library_id=library_id)

    category = params.get('category')
    if category and category not in ('all', '全部'):
        qs = qs.filter(library__category=category)

    if params.get('favorited') in ('1', 'true', 'True'):
        qs = qs.filter(favorites__isnull=False)

    keyword = (params.get('q') or '').strip()
    if keyword:
        qs = qs.filter(Q(name__icontains=keyword)
                       | Q(original_filename__icontains=keyword))

    if is_video and params.get('compatible') in ('1', 'true', 'True'):
        qs = qs.filter(browser_compatible=True)

    ordering = ORDERING_MAP.get(params.get('ordering') or 'recent', '-created_at')
    if not is_video and ordering in ('-duration', 'duration'):
        ordering = '-created_at'
    if is_video and ordering == '-taken_at':
        ordering = '-created_at'
    # 次级排序保证分页稳定（同值记录不会在页间跳动）
    return qs.order_by(ordering, '-created_at', 'id')


# ═══════════════════════════════════════════════════════
# 媒体库 CRUD
# ═══════════════════════════════════════════════════════

class MediaLibraryViewSet(viewsets.ModelViewSet):
    serializer_class = MediaLibrarySerializer

    def get_queryset(self):
        qs = MediaLibrary.objects.annotate(
            video_total=Count('videos', distinct=True),
            photo_total=Count('photos', distinct=True),
        )
        lib_type = self.request.query_params.get('type')
        if lib_type in ('video', 'photo'):
            qs = qs.filter(library_type=lib_type)
        return qs

    def perform_destroy(self, instance):
        """
        删除库配置.

        默认连带清理该库下的编目记录与缩略图（物理文件绝不动），
        传 ?keep_items=1 则只解绑，记录保留为"未分类"。
        """
        keep = self.request.query_params.get('keep_items') in ('1', 'true', 'True')
        if not keep:
            for model in (Video, Photo):
                items = model.objects.filter(library_id=instance.id)
                for obj in items.only('id', 'cover_path').iterator():
                    if obj.cover_path and os.path.isfile(obj.cover_path):
                        try:
                            os.remove(obj.cover_path)
                        except OSError:
                            pass
                items.delete()
        instance.delete()


@api_view(['POST'])
def pick_and_scan_library(request):
    """选择本机目录，按内容创建视频/图片库并立即扫描新建库。"""
    if not _folder_dialog_lock.acquire(blocking=False):
        return _bad('系统文件夹选择器已打开，请先完成选择', 409)
    try:
        folder_path, dialog_error = _choose_folder_with_system_dialog()
    finally:
        _folder_dialog_lock.release()
    if dialog_error:
        return _bad(dialog_error, 501)
    if not folder_path:
        return Response({'cancelled': True})
    if not os.path.isdir(folder_path):
        return _bad('所选文件夹不存在或当前无法访问', 404)

    try:
        counts = _detect_library_types(folder_path)
    except OSError:
        return _bad('无法读取所选文件夹', 409)
    library_types = [kind for kind, count in counts.items() if count > 0]
    if not library_types:
        return _bad('所选文件夹及其子文件夹中没有可识别的视频或图片', 400)

    base_name = os.path.basename(folder_path) or folder_path
    labels = {'video': '视频', 'photo': '图片'}
    libraries = []
    for library_type in library_types:
        library = MediaLibrary.objects.filter(
            folder_path=folder_path, library_type=library_type,
        ).first()
        if library is None:
            name = base_name if len(library_types) == 1 else f'{base_name}（{labels[library_type]}）'
            library = MediaLibrary.objects.create(
                name=name,
                folder_path=folder_path,
                library_type=library_type,
                enabled=True,
            )
        elif not library.enabled:
            library.enabled = True
            library.save(update_fields=['enabled'])
        libraries.append(library)

    scan = start_scan([str(library.id) for library in libraries])
    return Response({
        'cancelled': False,
        'libraries': MediaLibrarySerializer(libraries, many=True).data,
        'detected': counts,
        'scan': scan,
    }, status=202)


# ═══════════════════════════════════════════════════════
# 视频
# ═══════════════════════════════════════════════════════

class VideoListView(MediaListMixin, generics.ListAPIView):
    serializer_class = VideoSerializer
    content_type = ContentType.VIDEO

    def get_queryset(self):
        qs = Video.objects.select_related('library').all()
        return _apply_common_filters(qs, self.request.query_params, is_video=True)


class VideoDetailView(generics.RetrieveAPIView):
    serializer_class = VideoSerializer
    queryset = Video.objects.select_related('library').all()
    lookup_url_kwarg = 'video_id'

    def get_serializer_context(self):
        obj_id = self.kwargs.get('video_id')
        progress = {
            h.video_id: (h.position, h.percent)
            for h in HistoryEntry.objects.filter(
                video_id=obj_id, action=HistoryEntry.ActionType.PLAY)
        }
        return {
            'request': self.request,
            'check_files': True,
            'favorited_ids': set(
                Favorite.objects.filter(video_id=obj_id)
                .values_list('video_id', flat=True)),
            'progress_map': progress,
        }


@api_view(['POST'])
def video_rename(request, video_id):
    video = Video.objects.filter(id=video_id).first()
    if video is None:
        return _bad('视频不存在', 404)
    result = rename_file(video, request.data.get('name') or '')
    if 'error' in result:
        return Response(result, status=409)
    return Response({'success': True, 'video': VideoSerializer(video).data})


@api_view(['POST'])
def video_move(request, video_id):
    video = Video.objects.filter(id=video_id).first()
    if video is None:
        return _bad('视频不存在', 404)
    target_id = request.data.get('library_id')
    if not target_id:
        return _bad('请选择目标媒体库')
    target = MediaLibrary.objects.filter(id=target_id).first()
    if target is None:
        return _bad('目标媒体库不存在', 404)
    if target.library_type != MediaLibrary.LibraryType.VIDEO:
        return _bad('目标库不是视频库')

    result = move_file(video, target)
    if 'task_id' in result:
        return Response(result, status=202)
    if 'error' in result:
        return Response(result, status=409)
    video.refresh_from_db()
    return Response({'success': True, 'video': VideoSerializer(video).data})


@api_view(['DELETE'])
def video_delete(request, video_id):
    video = Video.objects.filter(id=video_id).first()
    if video is None:
        return _bad('视频不存在', 404)
    result = delete_file(video)
    if 'error' in result:
        return Response(result, status=409)
    return Response(result)


# ═══════════════════════════════════════════════════════
# 图片
# ═══════════════════════════════════════════════════════

class PhotoListView(MediaListMixin, generics.ListAPIView):
    serializer_class = PhotoSerializer
    content_type = ContentType.PHOTO

    def get_queryset(self):
        qs = Photo.objects.select_related('library').all()
        return _apply_common_filters(qs, self.request.query_params, is_video=False)


@api_view(['POST'])
def photo_rename(request, photo_id):
    photo = Photo.objects.filter(id=photo_id).first()
    if photo is None:
        return _bad('图片不存在', 404)
    result = rename_file(photo, request.data.get('name') or '')
    if 'error' in result:
        return Response(result, status=409)
    return Response({'success': True, 'photo': PhotoSerializer(photo).data})


@api_view(['POST'])
def photo_move(request, photo_id):
    photo = Photo.objects.filter(id=photo_id).first()
    if photo is None:
        return _bad('图片不存在', 404)
    target_id = request.data.get('library_id')
    if not target_id:
        return _bad('请选择目标相册')
    target = MediaLibrary.objects.filter(id=target_id).first()
    if target is None:
        return _bad('目标相册不存在', 404)
    if target.library_type != MediaLibrary.LibraryType.PHOTO:
        return _bad('目标库不是图片库')

    result = move_file(photo, target)
    if 'task_id' in result:
        return Response(result, status=202)
    if 'error' in result:
        return Response(result, status=409)
    photo.refresh_from_db()
    return Response({'success': True, 'photo': PhotoSerializer(photo).data})


@api_view(['DELETE'])
def photo_delete(request, photo_id):
    photo = Photo.objects.filter(id=photo_id).first()
    if photo is None:
        return _bad('图片不存在', 404)
    result = delete_file(photo)
    if 'error' in result:
        return Response(result, status=409)
    return Response(result)


# ═══════════════════════════════════════════════════════
# 缩略图 / 原图 / 视频流
# ═══════════════════════════════════════════════════════

@api_view(['GET'])
def serve_video_thumbnail(request, video_id):
    video = Video.objects.filter(id=video_id).only('cover_path').first()
    if video is None or not video.cover_path:
        raise Http404('缩略图不存在')
    return serve_media_file(request, video.cover_path)


@api_view(['GET'])
def serve_photo_thumbnail(request, photo_id):
    photo = Photo.objects.filter(id=photo_id).only('cover_path').first()
    if photo is None or not photo.cover_path:
        raise Http404('缩略图不存在')
    return serve_media_file(request, photo.cover_path)


@api_view(['GET', 'HEAD'])
def stream_video(request, video_id):
    """视频出流 — 支持 206 Range，浏览器可正常拖拽进度条."""
    video = Video.objects.filter(id=video_id).first()
    if video is None:
        raise Http404('视频不存在')
    return serve_media_file(request, video.absolute_path, video.original_filename)


@api_view(['POST'])
def open_video_with_default_player(request, video_id):
    """通过 Windows 文件关联交给该视频类型的系统默认播放器打开."""
    video = Video.objects.filter(id=video_id).only('absolute_path').first()
    if video is None:
        raise Http404('视频不存在')
    if not os.path.isfile(video.absolute_path):
        raise Http404('文件不存在或磁盘未连接')
    if os.name != 'nt' or not hasattr(os, 'startfile'):
        return _bad('此功能仅支持 Windows 本机环境', 501)

    try:
        os.startfile(video.absolute_path)
    except OSError:
        return _bad('无法调用系统默认播放器，请确认已为此类视频设置默认应用', 409)
    return Response({'success': True})


@api_view(['GET', 'HEAD'])
def serve_photo_original(request, photo_id):
    """图片原图 — 大图查看器用."""
    photo = Photo.objects.filter(id=photo_id).first()
    if photo is None:
        raise Http404('图片不存在')
    return serve_media_file(request, photo.absolute_path, photo.original_filename)


# ═══════════════════════════════════════════════════════
# 扫描（纯手动触发）
# ═══════════════════════════════════════════════════════

@api_view(['POST'])
def trigger_scan(request):
    result = start_scan()
    return Response(result, status=202)


@api_view(['GET'])
def scan_progress(request, task_id):
    data = get_scan_progress(task_id)
    if data is None:
        return _bad('扫描任务不存在或已过期', 404)
    return Response(data)


@api_view(['POST'])
def cancel_scan(request, task_id):
    if not request_cancel(task_id):
        return _bad('该任务已结束，无法停止', 409)
    return Response({'success': True, 'message': '正在停止扫描…'})


@api_view(['GET'])
def scan_status(request):
    """当前是否有扫描在跑 + 最近一次扫描结果（刷新页面后恢复显示）."""
    last = ScanRecord.objects.first()
    return Response({
        'active': get_active_scan(),
        'last_scan': ScanRecordSerializer(last).data if last else None,
    })


@api_view(['GET'])
def move_progress(request, task_id):
    data = get_move_progress(task_id)
    if data is None:
        return _bad('移动任务不存在或已过期', 404)
    return Response(data)


# ═══════════════════════════════════════════════════════
# 收藏
# ═══════════════════════════════════════════════════════

@api_view(['POST'])
def toggle_favorite(request):
    content_type = request.data.get('content_type')
    object_id = request.data.get('object_id')
    if content_type not in ('video', 'photo') or not object_id:
        return _bad('参数错误')

    if content_type == 'video':
        existing = Favorite.objects.filter(video_id=object_id).first()
    else:
        existing = Favorite.objects.filter(photo_id=object_id).first()

    if existing:
        existing.delete()
        return Response({'favorited': False})

    model = Video if content_type == 'video' else Photo
    if not model.objects.filter(id=object_id).exists():
        return _bad('目标不存在', 404)

    kwargs = ({'video_id': object_id} if content_type == 'video'
              else {'photo_id': object_id})
    fav = Favorite.objects.create(content_type=content_type, **kwargs)
    return Response({'favorited': True, 'favorite_id': str(fav.id)})


class FavoriteListView(NestedListMixin, generics.ListAPIView):
    serializer_class = FavoriteSerializer

    def get_queryset(self):
        qs = (Favorite.objects
              .select_related('video', 'video__library', 'photo', 'photo__library'))
        ctype = self.request.query_params.get('content_type')
        if ctype in ('video', 'photo'):
            qs = qs.filter(content_type=ctype)
        return qs


# ═══════════════════════════════════════════════════════
# 历史记录
# ═══════════════════════════════════════════════════════

@api_view(['POST'])
def record_history(request):
    """
    记录浏览/播放，同一对象同一动作只保留一条并累加次数.

    播放时可带 position/duration 保存进度，前端用来显示"看到 1:32:45"
    和继续观看。
    """
    content_type = request.data.get('content_type')
    object_id = request.data.get('object_id')
    action = request.data.get('action') or 'view'
    if content_type not in ('video', 'photo') or not object_id:
        return _bad('参数错误')
    if action not in ('view', 'play'):
        return _bad('action 只能是 view 或 play')

    model = Video if content_type == 'video' else Photo
    target = model.objects.filter(id=object_id).first()
    if target is None:
        return _bad('目标不存在', 404)

    try:
        position = float(request.data.get('position') or 0)
    except (TypeError, ValueError):
        position = 0.0

    percent = 0.0
    duration = getattr(target, 'duration', None) or 0
    if duration > 0 and position > 0:
        percent = round(min(position / duration * 100, 100), 2)

    lookup = ({'video_id': object_id} if content_type == 'video'
              else {'photo_id': object_id})
    entry = HistoryEntry.objects.filter(action=action, **lookup).first()

    if entry is None:
        entry = HistoryEntry.objects.create(
            content_type=content_type, action=action,
            position=position, percent=percent, **lookup)
    else:
        entry.play_count += 1
        # 只有明确带了进度才覆盖，避免"打开即清零"
        if position > 0:
            entry.position = position
            entry.percent = percent
        entry.save(update_fields=['play_count', 'position', 'percent', 'last_seen_at'])

    return Response(HistorySerializer(entry).data, status=201)


@api_view(['POST'])
def update_progress(request, video_id):
    """
    播放中定时上报进度（轻量端点，不累加播放次数）.
    """
    video = Video.objects.filter(id=video_id).only('id', 'duration').first()
    if video is None:
        return _bad('视频不存在', 404)
    try:
        position = float(request.data.get('position') or 0)
    except (TypeError, ValueError):
        return _bad('position 必须是数字')

    duration = video.duration or 0
    percent = round(min(position / duration * 100, 100), 2) if duration > 0 else 0.0

    entry, created = HistoryEntry.objects.get_or_create(
        video_id=video.id, action=HistoryEntry.ActionType.PLAY,
        defaults={'content_type': 'video', 'position': position, 'percent': percent},
    )
    if not created:
        entry.position = position
        entry.percent = percent
        entry.save(update_fields=['position', 'percent', 'last_seen_at'])
    return Response({'success': True, 'position': position, 'percent': percent})


class HistoryListView(NestedListMixin, generics.ListAPIView):
    serializer_class = HistorySerializer

    def get_queryset(self):
        qs = (HistoryEntry.objects
              .select_related('video', 'video__library', 'photo', 'photo__library'))
        action = self.request.query_params.get('action')
        if action in ('view', 'play'):
            qs = qs.filter(action=action)
        ctype = self.request.query_params.get('content_type')
        if ctype in ('video', 'photo'):
            qs = qs.filter(content_type=ctype)
        return qs


@api_view(['DELETE'])
def delete_history_entry(request, entry_id):
    deleted, _ = HistoryEntry.objects.filter(id=entry_id).delete()
    if not deleted:
        return _bad('记录不存在', 404)
    return Response({'success': True})


@api_view(['DELETE'])
def clear_history(request):
    """清空历史（可按 action / content_type 局部清空）."""
    qs = HistoryEntry.objects.all()
    action = request.query_params.get('action')
    if action in ('view', 'play'):
        qs = qs.filter(action=action)
    ctype = request.query_params.get('content_type')
    if ctype in ('video', 'photo'):
        qs = qs.filter(content_type=ctype)
    count = qs.count()
    qs.delete()
    return Response({'success': True, 'deleted': count})


# ═══════════════════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════════════════

@api_view(['GET'])
def search(request):
    """跨视频 + 图片的本地模糊搜索（名称与原始文件名）."""
    q = (request.GET.get('q') or '').strip()
    if not q:
        return Response({'videos': [], 'photos': [], 'total': 0, 'query': ''})

    scope = request.GET.get('scope') or 'all'
    limit = 40
    cond = Q(name__icontains=q) | Q(original_filename__icontains=q)

    videos, photos = [], []
    if scope in ('all', 'video'):
        videos = list(Video.objects.select_related('library').filter(cond)[:limit])
    if scope in ('all', 'photo'):
        photos = list(Photo.objects.select_related('library').filter(cond)[:limit])

    v_ctx = {
        'request': request,
        'favorited_ids': set(
            Favorite.objects.filter(video_id__in=[v.id for v in videos])
            .values_list('video_id', flat=True)),
        'progress_map': {
            h.video_id: (h.position, h.percent)
            for h in HistoryEntry.objects.filter(
                video_id__in=[v.id for v in videos], action='play')
        },
    }
    p_ctx = {
        'request': request,
        'favorited_ids': set(
            Favorite.objects.filter(photo_id__in=[p.id for p in photos])
            .values_list('photo_id', flat=True)),
    }

    return Response({
        'query': q,
        'videos': VideoSerializer(videos, many=True, context=v_ctx).data,
        'photos': PhotoSerializer(photos, many=True, context=p_ctx).data,
        'total': len(videos) + len(photos),
    })


# ═══════════════════════════════════════════════════════
# 统计 / 系统信息
# ═══════════════════════════════════════════════════════

@api_view(['GET'])
def stats(request):
    """首页与设置页的汇总数据."""
    video_agg = Video.objects.aggregate(n=Count('id'), size=Sum('file_size'),
                                        secs=Sum('duration'))
    photo_agg = Photo.objects.aggregate(n=Count('id'), size=Sum('file_size'))

    db_path = dj_settings.DATABASES['default']['NAME']
    db_size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0

    app_data = str(dj_settings.APP_DATA_DIR)
    cache_size, cache_files = 0, 0
    if os.path.isdir(app_data):
        for entry in os.scandir(app_data):
            if entry.is_file():
                cache_files += 1
                try:
                    cache_size += entry.stat().st_size
                except OSError:
                    pass

    return Response({
        'video_count': video_agg['n'] or 0,
        'photo_count': photo_agg['n'] or 0,
        'video_size': video_agg['size'] or 0,
        'photo_size': photo_agg['size'] or 0,
        'total_duration': video_agg['secs'] or 0,
        'favorite_count': Favorite.objects.count(),
        'history_count': HistoryEntry.objects.count(),
        'library_count': MediaLibrary.objects.count(),
        'incompatible_count': Video.objects.filter(browser_compatible=False).count(),
        'db_size': db_size,
        'cache_size': cache_size,
        'cache_files': cache_files,
        'app_data_dir': app_data,
        'ffmpeg': ffmpeg_available(),
        'offline': True,
        'server_time': timezone.now().isoformat(),
    })


@api_view(['POST'])
def clear_thumbnail_cache(request):
    """
    清空缩略图缓存 —— 只删 .app_data/ 内的文件，绝不触碰原始媒体.

    清完后同时把 cover_path 置空，下次扫描会重新生成。
    """
    app_data = str(dj_settings.APP_DATA_DIR)
    removed = 0
    if os.path.isdir(app_data):
        for entry in os.scandir(app_data):
            if entry.is_file() and entry.name.endswith('_thumb.jpg'):
                try:
                    os.remove(entry.path)
                    removed += 1
                except OSError:
                    pass
    Video.objects.exclude(cover_path='').update(cover_path='')
    Photo.objects.exclude(cover_path='').update(cover_path='')
    return Response({'success': True, 'removed': removed,
                     'message': f'已清理 {removed} 个缩略图，重新扫描后会自动重建'})


@api_view(['POST'])
def cleanup_orphans(request):
    """清理物理文件已不存在的编目记录（含所属库被删除的孤立项）."""
    removed = 0
    for model in (Video, Photo):
        for obj in model.objects.only('id', 'absolute_path', 'cover_path').iterator():
            if os.path.isfile(obj.absolute_path):
                continue
            if obj.cover_path and os.path.isfile(obj.cover_path):
                try:
                    os.remove(obj.cover_path)
                except OSError:
                    pass
            obj.delete()
            removed += 1
    return Response({'success': True, 'removed': removed,
                     'message': f'已清理 {removed} 条失效记录'})


# ═══════════════════════════════════════════════════════
# 应用设置（键值对）
# ═══════════════════════════════════════════════════════

DEFAULT_SETTINGS = {
    'playback': {
        'autoplay': False,
        'default_volume': 80,
        'seek_step': 10,
        'remember_position': True,
    },
    'appearance': {
        'grid_density': 'comfortable',   # compact | comfortable | spacious
        'show_filename': False,
    },
    'scan': {
        'generate_video_thumbnails': True,
        'skip_hidden': True,
    },
}


@api_view(['GET', 'PUT', 'PATCH'])
def app_settings(request):
    """读取/更新应用偏好，缺失的键回落到默认值."""
    if request.method == 'GET':
        stored = {s.key: s.value for s in AppSetting.objects.all()}
        merged = {}
        for group, defaults in DEFAULT_SETTINGS.items():
            values = stored.get(group) or {}
            merged[group] = {
                **defaults,
                **{k: v for k, v in values.items() if k in defaults},
            }
        return Response(merged)

    payload = request.data or {}
    if not isinstance(payload, dict):
        return _bad('请求体必须是对象')

    updated = {}
    for group, values in payload.items():
        if group not in DEFAULT_SETTINGS:
            continue
        if not isinstance(values, dict):
            continue
        current = AppSetting.objects.filter(key=group).first()
        stored_values = (current.value if current else None) or {}
        base = {
            **DEFAULT_SETTINGS[group],
            **{k: v for k, v in stored_values.items() if k in DEFAULT_SETTINGS[group]},
        }
        # 只接受默认结构里已有的键，避免写入任意数据
        base.update({k: v for k, v in values.items() if k in DEFAULT_SETTINGS[group]})
        AppSetting.objects.update_or_create(key=group, defaults={'value': base})
        updated[group] = base

    return Response(updated)


# ═══════════════════════════════════════════════════════
# 文件夹浏览（挂载媒体库时选路径用）
# ═══════════════════════════════════════════════════════

@api_view(['GET'])
def browse_directory(request):
    """
    列出某个目录下的子文件夹，供设置页"选择文件夹"使用.

    仅在本机 127.0.0.1 上服务，不返回文件内容，只返回目录名与媒体计数。
    不传 path 则返回所有可用盘符。
    """
    path = (request.GET.get('path') or '').strip()

    if not path:
        drives = []
        for letter in string.ascii_uppercase:
            root = f'{letter}:\\'
            if os.path.exists(root):
                total = free = None
                try:
                    usage = shutil.disk_usage(root)
                    total, free = usage.total, usage.free
                except OSError:
                    pass
                drives.append({'name': root, 'path': root,
                               'total': total, 'free': free})
        return Response({'current': '', 'parent': None,
                         'drives': drives, 'directories': []})

    path = path.strip('"')
    if not os.path.isdir(path):
        return _bad('目录不存在或无法访问', 404)

    directories = []
    video_here = photo_here = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.startswith(('$', '.')):
                            continue
                        directories.append({'name': entry.name, 'path': entry.path})
                    elif entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in VIDEO_EXTENSIONS:
                            video_here += 1
                        elif ext in PHOTO_EXTENSIONS:
                            photo_here += 1
                except OSError:
                    continue
    except PermissionError:
        return _bad('没有访问该目录的权限', 403)
    except OSError as e:
        return _bad(f'读取目录失败: {e.strerror or e}', 400)

    directories.sort(key=lambda d: d['name'].lower())
    parent = os.path.dirname(path.rstrip('\\/')) or None
    if parent == path:
        parent = None

    return Response({
        'current': path,
        'parent': parent,
        'drives': [],
        'directories': directories,
        'video_files_here': video_here,
        'photo_files_here': photo_here,
    })
