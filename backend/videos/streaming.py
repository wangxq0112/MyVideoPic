"""
媒体流服务 — 支持 HTTP 206 Range 请求.

为什么由 Django 出流而不是让 Nginx 直接 alias 整个盘符:
  * alias D:/ 会把整块硬盘挂到 HTTP 上，任何能访问该端口的人都能遍历全盘，
    与"绝对隐私"直接冲突
  * 经 UUID 端点出流，只有已入库的文件可被读取，路径永不出现在 URL 里

性能上仍可交给 Nginx:
  开启 settings.USE_X_ACCEL 后，本模块只回响应头 + X-Accel-Redirect，
  实际字节由 Nginx 的 sendfile 零拷贝发送，Django 不占内存也不占线程。
"""
import mimetypes
import os
import re
from urllib.parse import quote

from django.conf import settings
from django.http import (
    FileResponse, Http404, HttpResponse,
    HttpResponseNotModified, StreamingHttpResponse,
)
from django.utils.http import http_date

_RANGE_RE = re.compile(r'bytes\s*=\s*(\d*)\s*-\s*(\d*)', re.IGNORECASE)

STREAM_CHUNK = 512 * 1024   # 512 KB

# 常见容器的 MIME 补充（Windows 注册表里常缺失，会导致返回错误的 Content-Type）
_EXTRA_MIME = {
    '.mkv': 'video/x-matroska',
    '.m4v': 'video/mp4',
    '.mov': 'video/quicktime',
    '.avi': 'video/x-msvideo',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
    '.webm': 'video/webm',
    '.ts': 'video/mp2t',
    '.m2ts': 'video/mp2t',
    '.rmvb': 'application/vnd.rn-realmedia-vbr',
    '.heic': 'image/heic',
    '.heif': 'image/heif',
    '.avif': 'image/avif',
    '.jfif': 'image/jpeg',
}


def guess_content_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in _EXTRA_MIME:
        return _EXTRA_MIME[ext]
    ctype, _ = mimetypes.guess_type(path)
    return ctype or 'application/octet-stream'


def _parse_range(header: str, size: int) -> tuple[int, int] | None:
    """
    解析 Range 头，返回闭区间 (start, end).

    None 表示无法满足（调用方应回 416）；无 Range 头由调用方提前处理.
    只处理单区间 —— 播放器拖拽只会发单区间.
    """
    m = _RANGE_RE.match(header or '')
    if not m:
        return None
    raw_start, raw_end = m.group(1), m.group(2)

    if not raw_start and not raw_end:
        return None

    if not raw_start:                      # bytes=-500 → 最后 500 字节
        length = int(raw_end)
        if length <= 0:
            return None
        start = max(size - length, 0)
        end = size - 1
    else:
        start = int(raw_start)
        end = int(raw_end) if raw_end else size - 1
        end = min(end, size - 1)

    if start > end or start >= size:
        return None
    return start, end


def _file_iterator(path: str, start: int, length: int, chunk_size: int = STREAM_CHUNK):
    """按块读取文件的指定区间，避免把大文件整体读进内存."""
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def _accel_path(abs_path: str) -> str | None:
    """
    把磁盘绝对路径映射成 Nginx internal location.

    D:\\Movies\\a.mp4 → /_protected/D/Movies/a.mp4
    需配合 nginx 中 alias 到对应盘符的 internal location.
    """
    drive, rest = os.path.splitdrive(abs_path)
    if not drive:
        return None
    letter = drive.rstrip(':').upper()
    rel = rest.replace('\\', '/').lstrip('/')
    prefix = getattr(settings, 'X_ACCEL_PREFIX', '/_protected')
    return f'{prefix}/{letter}/{quote(rel)}'


def serve_media_file(request, abs_path: str, download_name: str = '') -> HttpResponse:
    """
    带 Range 支持地发送一个本地文件.

    浏览器拖拽进度条依赖 206 + Content-Range；缺了它大文件只能从头缓冲，
    表现就是"拖动无效 / 整个页面卡死"。
    """
    if not abs_path or not os.path.isfile(abs_path):
        raise Http404('文件不存在或磁盘未连接')

    try:
        stat = os.stat(abs_path)
    except OSError:
        raise Http404('文件无法读取')

    size = stat.st_size
    ctype = guess_content_type(abs_path)
    etag = f'"{int(stat.st_mtime)}-{size}"'
    last_modified = http_date(stat.st_mtime)

    # 条件请求 —— 命中则省掉整段传输
    if request.headers.get('If-None-Match') == etag:
        resp = HttpResponseNotModified()
        resp['ETag'] = etag
        return resp

    range_header = request.headers.get('Range')
    filename = download_name or os.path.basename(abs_path)
    # RFC 5987 —— 中文文件名必须编码，否则 Header 会抛 UnicodeEncodeError
    # 一律 inline：本应用只在页面内播放/查看，不提供下载入口
    cd = f"inline; filename*=UTF-8''{quote(filename)}"

    def finalize(resp):
        resp['Accept-Ranges'] = 'bytes'
        resp['ETag'] = etag
        resp['Last-Modified'] = last_modified
        resp['Content-Disposition'] = cd
        resp['Cache-Control'] = 'private, max-age=3600'
        # 本地播放器/浏览器直连，不需要嗅探保护之外的策略
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

    # ── Nginx 零拷贝路线 ──────────────────────────────
    if getattr(settings, 'USE_X_ACCEL', False):
        accel = _accel_path(abs_path)
        if accel:
            resp = HttpResponse(content_type=ctype)
            resp['X-Accel-Redirect'] = accel
            resp['X-Accel-Buffering'] = 'no'
            # Range 交给 Nginx 处理，Django 不再计算区间
            return finalize(resp)

    if range_header:
        rng = _parse_range(range_header, size)
        if rng is None:
            resp = HttpResponse(status=416, content_type=ctype)
            resp['Content-Range'] = f'bytes */{size}'
            resp['Accept-Ranges'] = 'bytes'
            return resp
        start, end = rng
        length = end - start + 1
        resp = StreamingHttpResponse(
            _file_iterator(abs_path, start, length),
            status=206, content_type=ctype,
        )
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = f'bytes {start}-{end}/{size}'
        return finalize(resp)

    resp = FileResponse(open(abs_path, 'rb'), content_type=ctype)
    resp['Content-Length'] = str(size)
    return finalize(resp)
