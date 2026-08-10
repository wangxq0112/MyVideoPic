"""
物理文件操作 — 重命名 / 移动 / 永久删除（视频与图片通用）.

三条硬性要求:
  1. 全部操作包 try...except，文件被占用时给出可读提示而非 500
  2. 跨盘符移动转入后台线程，按字节块拷贝并上报真实进度，绝不阻塞前台
  3. 缩略图以 UUID 命名存于 .app_data/，重命名与移动都无需重新生成
"""
import os
import shutil
import threading
import time
import uuid

# ── 跨盘移动任务表 ────────────────────────────────────
_move_tasks: dict[str, dict] = {}
_move_lock = threading.Lock()

_COPY_CHUNK = 4 * 1024 * 1024   # 4 MB

# Windows 文件名非法字符 —— 必须含路径分隔符，否则
# 用户输入 "..\\..\\x" 可把文件重命名到目录树之外
FORBIDDEN_CHARS = {'<', '>', ':', '"', '|', '?', '*', '/', '\\', '\0'}

# Windows 保留设备名（不区分大小写，含扩展名时同样保留）
RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *{f'COM{i}' for i in range(1, 10)},
    *{f'LPT{i}' for i in range(1, 10)},
}

MAX_NAME_LENGTH = 200


def _is_cross_drive(src: str, dst: str) -> bool:
    return os.path.splitdrive(src)[0].lower() != os.path.splitdrive(dst)[0].lower()


def validate_filename(name: str) -> str | None:
    """
    校验用户输入的新文件名（不含扩展名）.

    返回错误信息字符串；合法则返回 None.
    """
    name = name.strip()
    if not name:
        return '名称不能为空'
    if len(name) > MAX_NAME_LENGTH:
        return f'名称过长（最多 {MAX_NAME_LENGTH} 个字符）'

    bad = sorted({c for c in name if c in FORBIDDEN_CHARS or ord(c) < 32})
    if bad:
        shown = ' '.join(repr(c) if ord(c) < 32 else c for c in bad)
        return f'名称包含非法字符: {shown}'

    if name in ('.', '..'):
        return '名称不合法'
    if name.split('.')[0].upper() in RESERVED_NAMES:
        return f'"{name}" 是系统保留名称，请改用其他名称'
    if name.endswith(('.', ' ')):
        return '名称不能以空格或英文句点结尾'
    return None


# ═══════════════════════════════════════════════════════
# 重命名
# ═══════════════════════════════════════════════════════

def rename_file(obj, new_name: str) -> dict:
    """重命名物理文件并同步数据库（缩略图按 UUID 命名，无需处理）."""
    new_name = (new_name or '').strip()
    err = validate_filename(new_name)
    if err:
        return {'error': err}

    old_path = obj.absolute_path
    if not os.path.isfile(old_path):
        return {'error': '物理文件不存在，可能已被移动或删除，请重新扫描'}

    ext = os.path.splitext(obj.original_filename)[1]
    new_filename = new_name + ext
    new_path = os.path.join(os.path.dirname(old_path), new_filename)

    # 确认拼出的路径仍在原目录内（纵深防御）
    old_dir = os.path.normcase(os.path.dirname(os.path.abspath(old_path)))
    new_dir = os.path.normcase(os.path.dirname(os.path.abspath(new_path)))
    if old_dir != new_dir:
        return {'error': '名称不合法：不允许包含路径'}

    if os.path.normcase(old_path) == os.path.normcase(new_path):
        return {'error': '新名称与当前名称相同'}

    # Windows 大小写不敏感，仅改大小写时 os.path.exists 会误判为已存在
    only_case_change = old_path.lower() == new_path.lower()
    if not only_case_change and os.path.exists(new_path):
        return {'error': f'同目录下已存在同名文件: {new_filename}'}

    try:
        os.rename(old_path, new_path)
    except PermissionError:
        return {'error': '文件正被其他程序占用，请关闭播放器后重试'}
    except FileExistsError:
        return {'error': f'同目录下已存在同名文件: {new_filename}'}
    except OSError as e:
        return {'error': f'重命名失败: {e.strerror or e}'}

    obj.name = new_name
    obj.original_filename = new_filename
    obj.absolute_path = new_path
    obj.save(update_fields=['name', 'original_filename', 'absolute_path', 'updated_at'])
    return {'success': True}


# ═══════════════════════════════════════════════════════
# 移动
# ═══════════════════════════════════════════════════════

def move_file(obj, target_library) -> dict:
    """
    移动到目标库文件夹.

    同盘 → os.rename 瞬间完成（同步返回）
    跨盘 → 后台线程按块拷贝并上报进度（返回 task_id）
    """
    old_path = obj.absolute_path
    if not os.path.isfile(old_path):
        return {'error': '物理文件不存在，可能已被移动或删除，请重新扫描'}

    target_dir = target_library.folder_path
    if not os.path.isdir(target_dir):
        return {'error': '目标文件夹不存在或磁盘未连接'}

    new_path = os.path.join(target_dir, obj.original_filename)
    if os.path.normcase(os.path.abspath(old_path)) == os.path.normcase(os.path.abspath(new_path)):
        return {'error': '文件已在该库中'}
    if os.path.exists(new_path):
        return {'error': f'目标文件夹已存在同名文件: {obj.original_filename}'}

    if _is_cross_drive(old_path, new_path):
        try:
            total_bytes = os.path.getsize(old_path)
        except OSError:
            total_bytes = 0
        task_id = uuid.uuid4().hex[:12]
        with _move_lock:
            _move_tasks[task_id] = {
                'task_id': task_id, 'status': 'running',
                'message': f'跨盘移动中 — {obj.original_filename}',
                'filename': obj.original_filename,
                'copied_bytes': 0, 'total_bytes': total_bytes,
                'percent': 0.0, 'started_at': time.time(), 'eta_seconds': None,
            }
        threading.Thread(
            target=_cross_drive_move,
            args=(task_id, type(obj), obj.pk, old_path, new_path, target_library.pk),
            daemon=True, name=f'move-{task_id}',
        ).start()
        return {'task_id': task_id, 'status': 'running',
                'cross_drive': True, 'message': '跨盘移动已在后台启动'}

    try:
        os.rename(old_path, new_path)
    except PermissionError:
        return {'error': '文件正被其他程序占用，请关闭播放器后重试'}
    except OSError as e:
        return {'error': f'移动失败: {e.strerror or e}'}

    obj.absolute_path = new_path
    obj.library = target_library
    obj.save(update_fields=['absolute_path', 'library', 'updated_at'])
    return {'success': True, 'cross_drive': False}


def _cross_drive_move(task_id, model, obj_pk, src, dst, target_library_pk):
    """
    后台跨盘移动 — 分块拷贝上报进度，成功后再删源文件.

    重新查库而不复用主线程的 obj 实例：Django 的模型实例不是线程安全的，
    且拷贝期间前台可能已经改过同一条记录。
    """
    copied = 0
    try:
        total = os.path.getsize(src)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            while True:
                chunk = fsrc.read(_COPY_CHUNK)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)
                with _move_lock:
                    task = _move_tasks.get(task_id)
                    if task is not None:
                        task['copied_bytes'] = copied
                        task['percent'] = round(copied / total * 100, 1) if total else 0.0
                        elapsed = time.time() - task['started_at']
                        if copied and elapsed > 0:
                            rate = copied / elapsed
                            task['eta_seconds'] = int(max(total - copied, 0) / rate) if rate else None

        shutil.copystat(src, dst, follow_symlinks=True)

        # 内容已完整落盘，再删源文件
        try:
            os.remove(src)
        except PermissionError:
            with _move_lock:
                _move_tasks[task_id].update(
                    status='failed', percent=100.0,
                    message='目标已写入，但源文件正被占用无法删除，请手动清理源文件')
            return

        obj = model.objects.filter(pk=obj_pk).first()
        if obj is not None:
            obj.absolute_path = dst
            obj.library_id = target_library_pk
            obj.save(update_fields=['absolute_path', 'library', 'updated_at'])

        with _move_lock:
            _move_tasks[task_id].update(
                status='completed', percent=100.0,
                copied_bytes=copied, eta_seconds=0, message='跨盘移动完成')

    except Exception as e:                        # noqa: BLE001 — 后台线程兜底
        # 失败时清掉写了一半的目标文件，避免留下损坏残片
        try:
            if os.path.isfile(dst):
                os.remove(dst)
        except OSError:
            pass
        with _move_lock:
            if task_id in _move_tasks:
                _move_tasks[task_id].update(
                    status='failed', message=f'跨盘移动失败: {e}')


def get_move_progress(task_id: str) -> dict | None:
    with _move_lock:
        task = _move_tasks.get(task_id)
        return dict(task) if task else None


# ═══════════════════════════════════════════════════════
# 永久删除
# ═══════════════════════════════════════════════════════

def delete_file(obj) -> dict:
    """
    永久删除物理文件 + 缩略图 + 数据库记录（不进回收站）.

    顺序很关键：只有源文件确认删除（或本就不存在）才清理缩略图和记录，
    否则会出现"文件还在、编目已丢"的孤儿状态。
    """
    file_path = obj.absolute_path
    cover_path = obj.cover_path
    missing = False

    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except PermissionError:
            return {'error': '文件正被其他程序占用，请关闭播放器后重试'}
        except OSError as e:
            return {'error': f'删除文件失败: {e.strerror or e}'}
    else:
        missing = True

    # 走到这里说明磁盘上已无该文件 —— 可以安全清理缩略图与记录
    if cover_path and os.path.isfile(cover_path):
        try:
            os.remove(cover_path)
        except OSError:
            pass

    obj.delete()
    return {
        'success': True,
        'warning': '物理文件原本已不存在，仅清理了编目记录' if missing else '',
    }
