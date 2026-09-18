"""Decode and persist member images; never store client filenames or data URLs."""
from io import BytesIO
from pathlib import Path
import os
import secrets

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def image_directory() -> Path:
    return Path(os.environ.get('MEMBER_IMAGE_DIR', str(Path(__file__).resolve().parents[1] / 'uploads' / 'members')))


def save_image(content: bytes) -> str:
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, '图片不能超过 2MB')
    try:
        with Image.open(BytesIO(content)) as source:
            if source.format not in ('PNG', 'JPEG', 'WEBP', 'GIF'):
                raise HTTPException(422, '请选择 PNG、JPEG、WebP 或 GIF 图片')
            if source.width > 4096 or source.height > 4096:
                raise HTTPException(422, '图片宽高不能超过 4096 像素')
            source.load()
            # Strip client metadata, keep transparency, and normalize to PNG.
            clean = Image.new('RGBA', source.size)
            clean.paste(source.convert('RGBA'))
            output = BytesIO()
            clean.save(output, format='PNG')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, '图片文件无法解码') from None
    directory = image_directory()
    directory.mkdir(parents=True, exist_ok=True)
    filename = secrets.token_hex(24) + '.png'
    with (directory / filename).open('xb') as stream:
        stream.write(output.getvalue())
    return '/api/member-images/' + filename
