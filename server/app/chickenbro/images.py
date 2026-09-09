"""Chat-owned raster validation. Never fetch a user supplied URL."""
import base64
import binascii
import io
import warnings
from dataclasses import dataclass

MAX_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 3
MAX_PIXELS = 20_000_000
MAX_DATA_URL = 4 * ((MAX_BYTES + 2) // 3) + 32


class ImageError(ValueError):
    def __init__(self, code='CHAT_IMAGE_INVALID', message='请选择有效的 PNG 或 JPEG 图片，每张不超过 5 MiB。'):
        self.code, self.message = code, message
        super().__init__(message)


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    mime_type: str
    width: int
    height: int

    def data_url(self):
        return f'data:{self.mime_type};base64,' + base64.b64encode(self.data).decode('ascii')


def normalize_image(value: str) -> NormalizedImage:
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        raise ImageError('CHAT_IMAGES_DISABLED', '图片处理服务尚未就绪，请稍后再试。') from None
    if not isinstance(value, str) or len(value) > MAX_DATA_URL:
        raise ImageError()
    prefix, _, encoded = value.partition(',')
    formats = {'data:image/png;base64': 'PNG', 'data:image/jpeg;base64': 'JPEG'}
    if prefix not in formats:
        raise ImageError()
    try:
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > MAX_BYTES:
            raise ImageError()
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format != formats[prefix] or getattr(source, 'n_frames', 1) != 1:
                    raise ImageError()
                width, height = source.size
                if max(width, height) > 8192 or width * height > MAX_PIXELS:
                    raise ImageError()
                source.verify()
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                # A fresh raster removes EXIF, ICC, text, and all other metadata.
                mode = 'RGBA' if source.format == 'PNG' and ('A' in source.getbands() or 'transparency' in source.info) else 'RGB'
                converted = oriented.convert(mode)
                clean = Image.new(mode, converted.size)
                clean.paste(converted)
                output = io.BytesIO()
                clean.save(output, format=formats[prefix], **({'quality': 95} if formats[prefix] == 'JPEG' else {}))
                normalized = output.getvalue()
                if len(normalized) > MAX_BYTES:
                    raise ImageError()
                return NormalizedImage(normalized, prefix[5:-7], *clean.size)
    except (binascii.Error, OSError, ValueError, SyntaxError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, UnidentifiedImageError) as error:
        if isinstance(error, ImageError):
            raise
        raise ImageError() from None
