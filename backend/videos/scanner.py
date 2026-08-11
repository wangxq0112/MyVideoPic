"""
手动扫描引擎 — 后台线程执行 ffprobe 探测 / ffmpeg 截帧 / Pillow 缩略图 + 入库.

严格遵守项目约束:
  * 纯手动触发，无任何定时器或后台自动扫描
  * 原文件只读，缩略图一律写入 .app_data/ 并以数据库 UUID 命名
  * 全程离线，不请求任何外部 API

关键设计 —— 只清理"确认扫过"的库:
  若某个库所在磁盘离线（移动硬盘未插、网络盘断开），os.walk 会得到空结果。
  若此时按"DB 有但本次没扫到 = 已删除"的逻辑清理，会瞬间清空整个库的编目
  和缩略图。因此本模块只对成功遍历的库执行清理，离线库整体跳过并在结果中提示。
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .image_utils import generate_image_thumbnail

# ── 内存任务状态表（单用户本地应用，无需 Celery/Redis）──────
_scan_tasks: dict[str, dict] = {}
_lock = threading.RLock()
_active_task_id: str | None = None

# Windows 下隐藏 ffmpeg/ffprobe 子进程控制台窗口
_SUBPROCESS_FLAGS = {}
if os.name == 'nt':
    _SUBPROCESS_FLAGS['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

# ── 浏览器可尝试播放的组合 ─────────────────────────────
# 最终能力由前端对当前 Edge/Chrome 的 canPlayType() 判断。后端无法得知
# Windows HEVC 扩展、硬解能力和浏览器版本，因此这里只作为卡片初筛提示。
BROWSER_CONTAINERS = {'mp4', 'm4v', 'webm', 'ogg', 'ogv', 'mov', 'mkv'}
BROWSER_VIDEO_CODECS = {
    'h264', 'avc1', 'hevc', 'h265', 'hvc1', 'hev1', 'vp8', 'vp9', 'av1', 'theora',
}
BROWSER_AUDIO_CODECS = {
    'aac', 'mp3', 'mp4a', 'opus', 'vorbis', 'flac', 'pcm_s16le', 'ac3', 'eac3',
}

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
                    '.m4v', '.mpg', '.mpeg', '.ts', '.mts', '.m2ts', '.ogv',
                    '.3gp', '.3g2', '.f4v', '.rm', '.rmvb', '.asf', '.vob'}

# Pillow 能实际解码的格式（.svg 等矢量图不在此列，避免生成空封面）
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                    '.tiff', '.tif', '.ico', '.jfif', '.avif', '.heic', '.heif'}

# 跳过的系统/软件目录，避免把缓存缩略图当成媒体入库
SKIP_DIR_NAMES = {'.app_data', '$RECYCLE.BIN', 'System Volume Information',
                  '.git', 'node_modules', '__pycache__', '@eaDir'}

_YEAR_RE = re.compile(r'(?:\(|\[|\.|\s|_)((?:19|20)\d{2})(?:\)|\]|\.|\s|_|$)')

# 设置页里"扫描与更新"两个开关的默认值（与 views.DEFAULT_SETTINGS 一致）
_SCAN_DEFAULTS = {'generate_video_thumbnails': True, 'skip_hidden': True}


def _scan_settings() -> dict:
    """
    读取一次扫描相关偏好，整轮扫描期间保持不变.

    在扫描开始时快照，避免用户中途改设置导致同一批文件行为不一致。
    """
    from .models import AppSetting

    row = AppSetting.objects.filter(key='scan').first()
    stored = (row.value if row else None) or {}
    return {**_SCAN_DEFAULTS, **{k: v for k, v in stored.items() if k in _SCAN_DEFAULTS}}


def parse_year(filename: str) -> int | None:
    """从文件名推断年份，如 "教父.1972.1080p.mkv" → 1972."""
    matches = _YEAR_RE.findall(filename)
    if not matches:
        return None
    current = timezone.now().year + 1
    for m in matches:
        y = int(m)
        if 1900 <= y <= current:
            return y
    return None


def is_browser_compatible(container: str, video_codec: str, audio_codec: str) -> bool:
    """判断是否值得交给浏览器尝试；实际能力由前端按当前浏览器复核."""
    c = container.lower().lstrip('.')
    v = video_codec.lower().replace(' ', '')
    a = audio_codec.lower().replace(' ', '')
    return (
        c in BROWSER_CONTAINERS
        and (not v or v in BROWSER_VIDEO_CODECS)
        and (not a or a in BROWSER_AUDIO_CODECS)
    )


def ffmpeg_available() -> dict:
    """检测 ffmpeg / ffprobe 是否在 PATH 中（设置页系统信息用）."""
    return {
        'ffmpeg': shutil.which('ffmpeg') is not None,
        'ffprobe': shutil.which('ffprobe') is not None,
    }


# ═══════════════════════════════════════════════════════
# 媒体探测
# ═══════════════════════════════════════════════════════

def _run_ffprobe(filepath: str) -> dict | None:
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', filepath],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace', **_SUBPROCESS_FLAGS,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError):
        return None


def _parse_probe(probe: dict, filepath: str) -> dict:
    info = {'duration': None, 'width': None, 'height': None,
            'video_codec': '', 'audio_codec': '', 'container': ''}
    fmt = probe.get('format', {}) or {}

    info['container'] = os.path.splitext(filepath)[1].lstrip('.').lower()
    try:
        info['duration'] = float(fmt['duration']) if fmt.get('duration') else None
    except (TypeError, ValueError):
        info['duration'] = None

    for stream in probe.get('streams', []) or []:
        codec_type = stream.get('codec_type')
        if codec_type == 'video' and not info['video_codec']:
            # 封面图/附件流（mjpeg + attached_pic）不是真正的视频轨
            if stream.get('disposition', {}).get('attached_pic'):
                continue
            info['video_codec'] = stream.get('codec_name', '') or ''
            info['width'] = stream.get('width')
            info['height'] = stream.get('height')
            if info['duration'] is None and stream.get('duration'):
                try:
                    info['duration'] = float(stream['duration'])
                except (TypeError, ValueError):
                    pass
        elif codec_type == 'audio' and not info['audio_codec']:
            info['audio_codec'] = stream.get('codec_name', '') or ''
    return info


def _generate_video_thumbnail(video_path: str, video_uuid: str,
                              duration: float | None) -> str:
    """
    ffmpeg 截帧作为封面，输出到 .app_data/<uuid>_thumb.jpg.

    取 10% 处而非固定 5 秒 —— 短视频在第 5 秒可能已经结束，
    片头黑场也常导致纯黑封面。
    """
    thumb_dir = Path(settings.APP_DATA_DIR)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f'{video_uuid}_thumb.jpg'

    if duration and duration > 0:
        seek = min(max(duration * 0.1, 1.0), max(duration - 0.5, 0.0))
    else:
        seek = 1.0

    scale = 'scale=480:-2:force_original_aspect_ratio=decrease'
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-v', 'quiet',
             '-ss', f'{seek:.3f}', '-i', video_path,
             '-vframes', '1', '-vf', scale, '-q:v', '4',
             str(thumb_path)],
            check=True, timeout=60, capture_output=True, **_SUBPROCESS_FLAGS,
        )
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return str(thumb_path)
        # 生成了 0 字节文件 → 视为失败并清掉
        thumb_path.unlink(missing_ok=True)
        return ''
    except (subprocess.SubprocessError, OSError):
        try:
            thumb_path.unlink(missing_ok=True)
        except OSError:
            pass
        return ''


def _remove_cover(cover_path: str) -> None:
    if cover_path and os.path.isfile(cover_path):
        try:
            os.remove(cover_path)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════
# 任务状态
# ═══════════════════════════════════════════════════════

def _new_task_state(task_id: str) -> dict:
    return {
        'task_id': task_id,
        'status': 'pending',      # pending | running | completed | failed | cancelled
        'stage': 'prepare',       # prepare | walk | video | photo | cleanup | done
        'stage_label': '准备扫描…',
        'message': '准备扫描…',
        'current_file': '',
        'progress': 0,
        'total': 0,
        'percent': 0.0,
        'added': 0,
        'updated': 0,
        'removed': 0,
        'failed': 0,
        'skipped_libraries': [],
        'started_at': time.time(),
        'eta_seconds': None,
        'cancel_requested': False,
    }


def _update(task_id: str, **fields) -> None:
    with _lock:
        task = _scan_tasks.get(task_id)
        if task is None:
            return
        task.update(fields)
        total = task.get('total') or 0
        done = task.get('progress') or 0
        if total > 0:
            task['percent'] = round(min(done / total * 100, 100), 1)
            elapsed = time.time() - task['started_at']
            if done > 0 and task['status'] == 'running':
                task['eta_seconds'] = max(int(elapsed / done * (total - done)), 0)


def _is_cancelled(task_id: str) -> bool:
    with _lock:
        task = _scan_tasks.get(task_id)
        return bool(task and task['cancel_requested'])


def request_cancel(task_id: str) -> bool:
    with _lock:
        task = _scan_tasks.get(task_id)
        if not task or task['status'] not in ('pending', 'running'):
            return False
        task['cancel_requested'] = True
        task['message'] = '正在停止…'
        return True


def get_scan_progress(task_id: str) -> dict | None:
    with _lock:
        task = _scan_tasks.get(task_id)
        return dict(task) if task else None


def get_active_scan() -> dict | None:
    """返回当前进行中的扫描任务（前端刷新页面后可恢复进度显示）."""
    with _lock:
        if _active_task_id and _active_task_id in _scan_tasks:
            task = _scan_tasks[_active_task_id]
            if task['status'] in ('pending', 'running'):
                return dict(task)
    return None


# ═══════════════════════════════════════════════════════
# 文件遍历
# ═══════════════════════════════════════════════════════

def _walk_library(lib, skip_hidden: bool = True) -> tuple[list[str], str | None]:
    """
    遍历单个库目录.

    返回 (文件绝对路径列表, 错误原因)。错误原因非 None 时表示该库
    本次未能可靠遍历（离线/无权限），调用方必须跳过其清理步骤。
    """
    from .models import MediaLibrary

    folder = lib.folder_path
    if not folder or not os.path.isdir(folder):
        return [], '路径不存在或磁盘未连接'

    extensions = (VIDEO_EXTENSIONS
                  if lib.library_type == MediaLibrary.LibraryType.VIDEO
                  else PHOTO_EXTENSIONS)

    found: list[str] = []
    walk_error: str | None = None

    def on_error(err: OSError):
        nonlocal walk_error
        walk_error = f'{err.strerror or err}'

    for root, dirs, files in os.walk(folder, onerror=on_error):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIR_NAMES and not d.startswith('$')
                   and not (skip_hidden and d.startswith('.'))]
        for f in files:
            if skip_hidden and f.startswith('.'):
                continue
            if os.path.splitext(f)[1].lower() in extensions:
                found.append(os.path.join(root, f))

    if walk_error and not found:
        return [], f'读取失败: {walk_error}'
    return found, None


def _stat_file(path: str) -> tuple[int, float] | None:
    try:
        st = os.stat(path)
        return st.st_size, st.st_mtime
    except OSError:
        return None


# ═══════════════════════════════════════════════════════
# 主扫描流程
# ═══════════════════════════════════════════════════════

def scan_libraries(task_id: str, library_ids: tuple[str, ...] | None = None) -> None:
    """后台线程入口 — 增量扫描全部启用的库."""
    global _active_task_id
    from .models import MediaLibrary, Photo, ScanRecord, Video

    started = timezone.now()
    record_stats = {'added': 0, 'updated': 0, 'removed': 0, 'failed': 0, 'total': 0}
    final_status = 'completed'
    final_message = ''

    try:
        _update(task_id, status='running', stage='walk',
                stage_label='遍历文件夹', message='正在遍历媒体库文件夹…')

        prefs = _scan_settings()
        libraries_query = MediaLibrary.objects.filter(enabled=True)
        if library_ids is not None:
            libraries_query = libraries_query.filter(id__in=library_ids)
        libraries = list(libraries_query)
        if not libraries:
            _update(task_id, status='completed', stage='done', stage_label='完成',
                    message='没有启用的媒体库，请先在设置中添加文件夹', percent=100.0)
            final_message = '没有启用的媒体库'
            return

        video_targets: dict[str, str] = {}   # path -> library_id
        photo_targets: dict[str, str] = {}
        scanned_video_libs: list[str] = []   # 成功遍历的视频库 id
        scanned_photo_libs: list[str] = []
        skipped: list[dict] = []

        for lib in libraries:
            files, err = _walk_library(lib, prefs['skip_hidden'])
            if err:
                skipped.append({'name': lib.name, 'path': lib.folder_path, 'reason': err})
                continue
            if lib.library_type == MediaLibrary.LibraryType.VIDEO:
                scanned_video_libs.append(str(lib.id))
                for p in files:
                    video_targets[p] = str(lib.id)
            else:
                scanned_photo_libs.append(str(lib.id))
                for p in files:
                    photo_targets[p] = str(lib.id)

        total = len(video_targets) + len(photo_targets)
        record_stats['total'] = total
        _update(task_id, total=total, skipped_libraries=skipped,
                message=f'发现 {len(video_targets)} 个视频 + {len(photo_targets)} 张图片')

        if skipped and total == 0:
            names = '、'.join(s['name'] for s in skipped)
            _update(task_id, status='completed', stage='done', stage_label='完成',
                    percent=100.0,
                    message=f'以下媒体库无法访问，已跳过（编目未改动）: {names}')
            final_message = f'{len(skipped)} 个库无法访问，已跳过'
            return

        if total == 0:
            _update(task_id, status='completed', stage='done', stage_label='完成',
                    percent=100.0, message='未发现媒体文件')
            final_message = '未发现媒体文件'
            return

        done = 0

        # ── 视频 ──────────────────────────────────────
        _update(task_id, stage='video', stage_label='处理视频')
        for filepath, lib_id in video_targets.items():
            if _is_cancelled(task_id):
                break
            done += 1
            _update(task_id, progress=done, current_file=os.path.basename(filepath),
                    message=f'视频: {os.path.basename(filepath)}')
            outcome = _sync_video(filepath, lib_id,
                                  prefs['generate_video_thumbnails'])
            record_stats[outcome] = record_stats.get(outcome, 0) + 1
            _update(task_id, **{k: record_stats[k] for k in ('added', 'updated', 'failed')})

        # ── 图片 ──────────────────────────────────────
        if not _is_cancelled(task_id):
            _update(task_id, stage='photo', stage_label='处理图片')
        for filepath, lib_id in photo_targets.items():
            if _is_cancelled(task_id):
                break
            done += 1
            _update(task_id, progress=done, current_file=os.path.basename(filepath),
                    message=f'图片: {os.path.basename(filepath)}')
            outcome = _sync_photo(filepath, lib_id)
            record_stats[outcome] = record_stats.get(outcome, 0) + 1
            _update(task_id, **{k: record_stats[k] for k in ('added', 'updated', 'failed')})

        cancelled = _is_cancelled(task_id)

        # ── 清理：只针对本次成功遍历的库 ────────────────
        if not cancelled:
            _update(task_id, stage='cleanup', stage_label='清理失效记录',
                    current_file='', message='清理已不存在的文件记录…')
            record_stats['removed'] += _cleanup_missing(
                Video, scanned_video_libs, set(video_targets))
            record_stats['removed'] += _cleanup_missing(
                Photo, scanned_photo_libs, set(photo_targets))

            MediaLibrary.objects.filter(
                id__in=scanned_video_libs + scanned_photo_libs,
            ).update(last_scanned_at=timezone.now())

        summary = (f'新增 {record_stats["added"]} · 更新 {record_stats["updated"]} · '
                   f'清理 {record_stats["removed"]} · 失败 {record_stats["failed"]}')
        if skipped:
            summary += f' · {len(skipped)} 个库无法访问已跳过'

        final_status = 'cancelled' if cancelled else 'completed'
        final_message = ('已停止 — ' + summary) if cancelled else ('扫描完成 — ' + summary)
        _update(task_id, status=final_status, stage='done',
                stage_label='已停止' if cancelled else '完成',
                current_file='', message=final_message,
                removed=record_stats['removed'], eta_seconds=0)

    except Exception as exc:                      # noqa: BLE001 — 后台线程兜底
        final_status = 'failed'
        final_message = f'扫描异常: {exc}'
        _update(task_id, status='failed', stage='done', stage_label='失败',
                message=final_message)
    finally:
        finished = timezone.now()
        try:
            ScanRecord.objects.create(
                started_at=started, finished_at=finished,
                duration_seconds=round((finished - started).total_seconds(), 2),
                total_files=record_stats['total'], added=record_stats['added'],
                updated=record_stats['updated'], removed=record_stats['removed'],
                failed=record_stats['failed'], status=final_status,
                message=final_message[:512],
            )
            # 只保留最近 50 条扫描记录，避免无限增长
            stale = ScanRecord.objects.values_list('id', flat=True)[50:]
            if stale:
                ScanRecord.objects.filter(id__in=list(stale)).delete()
        except Exception:
            pass
        with _lock:
            if _active_task_id == task_id:
                _active_task_id = None
            _prune_tasks()


def _cleanup_missing(model, scanned_lib_ids: list[str], seen_paths: set[str]) -> int:
    """
    删除"属于本次已成功遍历的库、但磁盘上已不存在"的记录及其缩略图.

    刻意不处理 library_id 为空（库被删后 SET_NULL）或属于离线库的记录，
    避免误伤。孤立记录由用户在设置页手动清理。
    """
    if not scanned_lib_ids:
        return 0

    candidates = model.objects.filter(library_id__in=scanned_lib_ids)
    stale_ids, stale_covers = [], []
    for obj in candidates.only('id', 'absolute_path', 'cover_path').iterator():
        if obj.absolute_path in seen_paths:
            continue
        # 双重确认：路径确实不在磁盘上才删（防御 walk 的边缘遗漏）
        if os.path.exists(obj.absolute_path):
            continue
        stale_ids.append(obj.id)
        if obj.cover_path:
            stale_covers.append(obj.cover_path)

    if not stale_ids:
        return 0

    for cover in stale_covers:
        _remove_cover(cover)
    deleted, _ = model.objects.filter(id__in=stale_ids).delete()
    return len(stale_ids)


def _sync_video(filepath: str, lib_id: str, make_thumb: bool = True) -> str:
    """
    单个视频入库/更新.

    返回 'added' | 'updated' | 'skipped' | 'failed'.
    make_thumb=False 时跳过 ffmpeg 截帧（扫描快很多，卡片显示占位图）。
    """
    from .models import Video

    stat = _stat_file(filepath)
    if stat is None:
        return 'failed'
    size, mtime = stat

    existing = Video.objects.filter(absolute_path=filepath).first()
    if existing:
        unchanged = (existing.file_size == size
                     and abs((existing.file_mtime or 0) - mtime) < 1)
        has_cover = bool(existing.cover_path) and os.path.isfile(existing.cover_path)
        expected_compatibility = is_browser_compatible(
            existing.container_format, existing.video_codec, existing.audio_codec)
        if unchanged and (has_cover or not make_thumb) and str(existing.library_id) == lib_id:
            if existing.browser_compatible == expected_compatibility:
                return 'skipped'
            # 兼容规则升级后，未改动的已入库视频也要刷新卡片提示。
            existing.browser_compatible = expected_compatibility
            existing.save(update_fields=['browser_compatible'])
            return 'updated'

        probe = _run_ffprobe(filepath)
        if probe is None and not unchanged:
            return 'failed'
        if probe is not None:
            info = _parse_probe(probe, filepath)
            existing.duration = info['duration']
            existing.width = info['width']
            existing.height = info['height']
            existing.video_codec = info['video_codec']
            existing.audio_codec = info['audio_codec']
            existing.container_format = info['container']
            existing.browser_compatible = is_browser_compatible(
                info['container'], info['video_codec'], info['audio_codec'])
        existing.file_size = size
        existing.file_mtime = mtime
        existing.library_id = lib_id
        existing.year = existing.year or parse_year(existing.original_filename)
        if not has_cover and make_thumb:
            existing.cover_path = _generate_video_thumbnail(
                filepath, str(existing.id), existing.duration)
        existing.save()
        return 'updated'

    probe = _run_ffprobe(filepath)
    if probe is None:
        return 'failed'
    info = _parse_probe(probe, filepath)

    filename = os.path.basename(filepath)
    vid = Video(
        id=uuid.uuid4(),
        absolute_path=filepath,
        original_filename=filename,
        name=os.path.splitext(filename)[0],
        file_size=size,
        file_mtime=mtime,
        duration=info['duration'],
        width=info['width'],
        height=info['height'],
        video_codec=info['video_codec'],
        audio_codec=info['audio_codec'],
        container_format=info['container'],
        browser_compatible=is_browser_compatible(
            info['container'], info['video_codec'], info['audio_codec']),
        year=parse_year(filename),
        library_id=lib_id,
    )
    if make_thumb:
        vid.cover_path = _generate_video_thumbnail(
            filepath, str(vid.id), info['duration'])
    try:
        vid.save()
    except Exception:
        _remove_cover(vid.cover_path)
        return 'failed'
    return 'added'


def _sync_photo(filepath: str, lib_id: str) -> str:
    """单个图片入库/更新，返回 'added' | 'updated' | 'skipped' | 'failed'."""
    from .models import Photo

    stat = _stat_file(filepath)
    if stat is None:
        return 'failed'
    size, mtime = stat

    existing = Photo.objects.filter(absolute_path=filepath).first()
    if existing:
        unchanged = (existing.file_size == size
                     and abs((existing.file_mtime or 0) - mtime) < 1)
        has_cover = bool(existing.cover_path) and os.path.isfile(existing.cover_path)
        if unchanged and has_cover and str(existing.library_id) == lib_id:
            return 'skipped'

        cover, meta = generate_image_thumbnail(filepath, str(existing.id))
        existing.file_size = size
        existing.file_mtime = mtime
        existing.library_id = lib_id
        if cover:
            existing.cover_path = cover
        if meta.get('width'):
            existing.width = meta['width']
            existing.height = meta['height']
        existing.exif_orientation = meta.get('orientation')
        if meta.get('taken_at'):
            existing.taken_at = _aware(meta['taken_at'])
        existing.save()
        return 'updated'

    filename = os.path.basename(filepath)
    photo_id = uuid.uuid4()
    cover, meta = generate_image_thumbnail(filepath, str(photo_id))
    if not cover and not meta.get('width'):
        # 既没缩略图也读不到尺寸 → Pillow 完全无法识别，计入失败不入库
        return 'failed'

    photo = Photo(
        id=photo_id,
        absolute_path=filepath,
        original_filename=filename,
        name=os.path.splitext(filename)[0],
        file_size=size,
        file_mtime=mtime,
        cover_path=cover,
        width=meta.get('width'),
        height=meta.get('height'),
        exif_orientation=meta.get('orientation'),
        taken_at=_aware(meta['taken_at']) if meta.get('taken_at') else None,
        library_id=lib_id,
    )
    try:
        photo.save()
    except Exception:
        _remove_cover(cover)
        return 'failed'
    return 'added'


def _aware(dt):
    """EXIF 里的时间是本地朴素时间，补上当前时区避免 Django 警告."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        try:
            return timezone.make_aware(dt)
        except Exception:
            return None
    return dt


def _prune_tasks(keep: int = 20) -> None:
    """限制内存任务表长度（调用方需已持有 _lock）."""
    if len(_scan_tasks) <= keep:
        return
    ordered = sorted(_scan_tasks.items(), key=lambda kv: kv[1].get('started_at', 0))
    for tid, _ in ordered[:len(_scan_tasks) - keep]:
        _scan_tasks.pop(tid, None)


def start_scan(library_ids: list[str] | tuple[str, ...] | None = None) -> dict:
    """
    启动一次扫描。传入 library_ids 时只扫描指定媒体库。

    同一时刻只允许一个扫描任务；重复触发返回既有任务，避免并发写同一批记录。
    """
    global _active_task_id
    with _lock:
        active = get_active_scan()
        if active:
            return {'task_id': active['task_id'], 'status': active['status'],
                    'already_running': True}
        task_id = uuid.uuid4().hex[:12]
        _scan_tasks[task_id] = _new_task_state(task_id)
        _active_task_id = task_id

    target_ids = tuple(str(item) for item in library_ids) if library_ids is not None else None
    threading.Thread(target=scan_libraries, args=(task_id, target_ids),
                     daemon=True, name=f'scan-{task_id}').start()
    return {'task_id': task_id, 'status': 'started', 'already_running': False}
