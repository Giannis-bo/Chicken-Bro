"""Bounded raster avatars. No remote fetch, image decoder, or executable format.

Strip ancillary metadata (including EXIF) before persistence. The client renders
only the validated PNG/JPEG data URL through an image element.
"""
import base64
import binascii
import struct
import zlib

MAX_AVATAR_BYTES = 262144
MAX_AVATAR_DATA_URL = 349551
MAX_DIMENSION = 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _dimensions(width: int, height: int) -> None:
    if not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION:
        raise ValueError('avatar dimensions out of range')


def _png(data: bytes) -> bytes:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError('invalid PNG')
    offset, output, compressed = 8, bytearray(PNG_SIGNATURE), bytearray()
    header = None
    ended = False
    while offset + 12 <= len(data):
        size = int.from_bytes(data[offset:offset + 4], 'big')
        end = offset + size + 12
        if end > len(data): raise ValueError('truncated PNG')
        kind, payload = data[offset + 4:offset + 8], data[offset + 8:end - 4]
        if zlib.crc32(kind + payload) != int.from_bytes(data[end - 4:end], 'big'):
            raise ValueError('PNG checksum mismatch')
        if header is None:
            if kind != b'IHDR' or size != 13: raise ValueError('missing PNG header')
            header = struct.unpack('>IIBBBBB', payload)
            width, height, depth, color, compression, filtering, interlace = header
            _dimensions(width, height)
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            if depth not in depths.get(color, ()) or compression or filtering or interlace not in (0, 1):
                raise ValueError('unsupported PNG header')
        elif kind == b'IHDR': raise ValueError('duplicate PNG header')
        if kind == b'IDAT': compressed.extend(payload)
        if kind in (b'IHDR', b'PLTE', b'IDAT', b'IEND', b'tRNS'):
            output.extend(data[offset:end])
        elif not kind[0] & 32: raise ValueError('unknown PNG critical chunk')
        offset = end
        if kind == b'IEND':
            if size or offset != len(data): raise ValueError('invalid PNG end')
            ended = True
            break
    if not ended or not compressed or header is None: raise ValueError('incomplete PNG')
    # Limit decompression by actual dimensions, including Adam7 row overhead.
    width, height, depth, color, _, _, interlace = header
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    expected = ((width * channels * depth + 7) // 8 + 1) * height
    limit = expected if not interlace else (width * channels * 2 + 8) * (height + 8)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), limit + 1)
    if len(raw) > limit or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('invalid PNG pixel stream')
    if not interlace and len(raw) != expected: raise ValueError('invalid PNG pixel size')
    return bytes(output)


def _jpeg(data: bytes) -> bytes:
    if not data.startswith(b'\xff\xd8'): raise ValueError('invalid JPEG')
    output, offset, frame, scan = bytearray(data[:2]), 2, False, False
    while offset < len(data):
        start = offset
        if data[offset] != 255: raise ValueError('invalid JPEG marker')
        while offset < len(data) and data[offset] == 255: offset += 1
        if offset >= len(data): raise ValueError('truncated JPEG')
        marker = data[offset]
        offset += 1
        if marker == 0xd9:
            if not frame or not scan or offset != len(data): raise ValueError('incomplete JPEG')
            output.extend(b'\xff\xd9')
            return bytes(output)
        if marker not in (0xc0, 0xc1, 0xc2, 0xc4, 0xdb, 0xdd, 0xda, 0xfe) and not 0xe0 <= marker <= 0xef:
            raise ValueError('unsupported JPEG marker')
        if offset + 2 > len(data): raise ValueError('truncated JPEG segment')
        size = int.from_bytes(data[offset:offset + 2], 'big')
        end = offset + size
        if size < 2 or end > len(data): raise ValueError('invalid JPEG segment')
        if marker in (0xc0, 0xc1, 0xc2):
            if frame or size < 11: raise ValueError('invalid JPEG frame')
            _dimensions(int.from_bytes(data[offset + 5:offset + 7], 'big'), int.from_bytes(data[offset + 3:offset + 5], 'big'))
            if data[offset + 2] != 8 or data[offset + 7] not in (1, 3) or size != 8 + 3 * data[offset + 7]: raise ValueError('invalid JPEG components')
            frame = True
        if not (0xe0 <= marker <= 0xef or marker == 0xfe): output.extend(data[start:end])
        offset = end
        if marker == 0xda:
            if not frame or size < 8: raise ValueError('invalid JPEG scan')
            scan = True
            start = offset
            while offset < len(data):
                if data[offset] != 255:
                    offset += 1
                    continue
                next_byte = offset + 1
                while next_byte < len(data) and data[next_byte] == 255: next_byte += 1
                if next_byte >= len(data): raise ValueError('truncated JPEG scan')
                if data[next_byte] == 0 or 0xd0 <= data[next_byte] <= 0xd7:
                    offset = next_byte + 1
                else: break
            output.extend(data[start:offset])
    raise ValueError('missing JPEG end')


def normalize_avatar(value: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_AVATAR_DATA_URL:
        raise ValueError('avatar too large')
    prefix, separator, encoded = value.partition(',')
    if not separator or prefix not in ('data:image/png;base64', 'data:image/jpeg;base64'):
        raise ValueError('PNG or JPEG required')
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_AVATAR_BYTES: raise ValueError('avatar too large')
        normalized = _png(raw) if prefix == 'data:image/png;base64' else _jpeg(raw)
    except (binascii.Error, zlib.error, struct.error, IndexError) as error:
        raise ValueError('invalid avatar image') from error
    return prefix + ',' + base64.b64encode(normalized).decode('ascii')
