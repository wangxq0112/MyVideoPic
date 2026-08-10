"""
图片处理 — EXIF 方向修正 + 缩略图生成.

手机竖拍照片带 EXIF Orientation 标签，浏览器不会自动旋转，
若不修正会导致相册里横竖错乱。此处在生成缩略图时一次性纠正，
原文件全程只读（零侵入）。
"""
import datetime
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

# EXIF Orientation 标签值 → 人类可读说明
# 参考: https://www.impulseadventure.com/photo/exif-orientation.html
ORIENTATION_LABELS = {
    1: '正常',
    2: '水平翻转',
    3: '旋转 180°',
    4: '垂直翻转',
    5: '转置（90° CCW + 翻转）',
    6: '旋转 90° CW（手机竖拍常见）',
    7: '转置（90° CW + 翻转）',
    8: '旋转 90° CCW',
}

EXIF_ORIENTATION_TAG = 0x0112
EXIF_DATETIME_ORIGINAL_TAG = 0x9003
EXIF_DATETIME_TAG = 0x0132

# Pillow 无法解码的扩展名（矢量图 / 需额外插件的格式）
UNSUPPORTED_BY_PILLOW = {'.svg', '.svgz'}


def correct_orientation(image: Image.Image) -> Image.Image:
    """
    按 EXIF Orientation 旋转/翻转图片，返回修正后的新 Image.

    直接委托 Pillow 官方 ``ImageOps.exif_transpose``，它覆盖全部 8 种
    orientation 取值，并会顺带清理 EXIF 中已失效的方向标签。

    注意：Pillow 的 transpose 返回新对象而非原地修改，
    调用方必须接收返回值。
    """
    try:
        return ImageOps.exif_transpose(image) or image
    except Exception:
        return image


def read_exif_meta(image: Image.Image) -> dict:
    """读取 EXIF 中的方向与拍摄时间."""
    meta = {'orientation': None, 'taken_at': None}
    try:
        exif = image.getexif()
    except Exception:
        return meta
    if not exif:
        return meta

    meta['orientation'] = exif.get(EXIF_ORIENTATION_TAG)

    raw = None
    try:
        # DateTimeOriginal 位于 Exif IFD 子字典中
        sub = exif.get_ifd(0x8769)
        raw = sub.get(EXIF_DATETIME_ORIGINAL_TAG)
    except Exception:
        pass
    if not raw:
        raw = exif.get(EXIF_DATETIME_TAG)

    if raw:
        for fmt in ('%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                meta['taken_at'] = datetime.datetime.strptime(str(raw).strip(), fmt)
                break
            except (ValueError, TypeError):
                continue
    return meta


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    """
    把带透明通道 / 调色板 / 灰度16位等模式统一转成 RGB.

    JPEG 不支持 alpha，若不转换 ``save('JPEG')`` 会直接抛
    ``OSError: cannot write mode RGBA as JPEG``，导致 PNG 缩略图静默全失败.
    """
    if img.mode in ('RGBA', 'LA', 'PA'):
        background = Image.new('RGB', img.size, (18, 18, 24))
        alpha = img.convert('RGBA').getchannel('A')
        background.paste(img.convert('RGB'), mask=alpha)
        return background
    if img.mode == 'P':
        converted = img.convert('RGBA')
        return _flatten_to_rgb(converted)
    if img.mode != 'RGB':
        return img.convert('RGB')
    return img


def generate_image_thumbnail(source_path: str, image_uuid: str,
                             size: tuple[int, int] | None = None) -> tuple[str, dict]:
    """
    生成 EXIF 方向已修正的缩略图.

    参数:
        source_path: 原始图片绝对路径（只读）
        image_uuid:  数据库 UUID，用作缩略图文件名
        size:        缩略图最大边界 (宽, 高)

    返回:
        (缩略图路径, EXIF 元数据 dict)；失败时路径为空字符串.
        元数据始终尽力返回，便于即使缩略图失败也能记录尺寸/方向.
    """
    if size is None:
        size = getattr(settings, 'THUMBNAIL_SIZE', (480, 360))

    meta = {'orientation': None, 'taken_at': None, 'width': None, 'height': None}

    ext = Path(source_path).suffix.lower()
    if ext in UNSUPPORTED_BY_PILLOW:
        return '', meta

    thumb_dir = Path(settings.APP_DATA_DIR)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f'{image_uuid}_thumb.jpg'

    try:
        with Image.open(source_path) as img:
            exif_meta = read_exif_meta(img)
            meta.update(exif_meta)

            # 先修正方向，再取尺寸 —— 竖拍照片修正后宽高互换
            fixed = correct_orientation(img)
            meta['width'], meta['height'] = fixed.size

            fixed = _flatten_to_rgb(fixed)
            fixed.thumbnail(size, Image.Resampling.LANCZOS)
            # 不带 exif 参数保存 → 缩略图自动剥离元数据
            fixed.save(thumb_path, 'JPEG', quality=85, optimize=True)

        return str(thumb_path), meta

    except (UnidentifiedImageError, OSError, ValueError, MemoryError):
        # 格式不被支持 / 文件损坏 / 被占用 —— 交由调用方计入失败数
        return '', meta
    except Exception:
        return '', meta
