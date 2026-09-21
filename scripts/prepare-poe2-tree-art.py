"""Cloud-only: project pinned PoB release DDS array slices into a browser atlas.

Reads the existing official v0.23.1 portable archive. Does not fetch or execute it.
Game artwork belongs to Grinding Gear Games; engine license is retained alongside.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import subprocess
from zipfile import ZipFile
from PIL import Image

PIN = '7d6f530cbdab20389ff8bc6ba97a37ac27f74e41'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--pob', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert subprocess.check_output(['git', '-C', str(args.pob), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    tree_bytes = (args.pob / 'src/TreeData/0_5/tree.json').read_bytes()
    tree = json.loads(tree_bytes)
    source = ZipFile(args.archive)
    # Bind resource mapping to exactly the engine's tree, not just a release label.
    assert json.loads(source.read('TreeData/0_5/tree.json')) == tree
    images = {}
    for filename, mapping in tree['ddsCoords'].items():
        if not (filename.startswith('skills_') or filename.startswith('legion_') and '_BC1' in filename):
            continue
        dds = subprocess.run(['zstd', '-dc'], input=source.read('TreeData/0_5/' + filename), capture_output=True, check=True).stdout
        assert dds[:4] == b'DDS ' and dds[84:88] == b'DX10'
        height, width = struct.unpack_from('<II', dds, 12)
        mips = max(1, struct.unpack_from('<I', dds, 28)[0])
        fmt, _, _, count, _ = struct.unpack_from('<5I', dds, 128)
        assert fmt in (71, 72), 'Only BC1 icon sheets expected'
        stride = sum(max(1, ((width >> level) + 3) // 4) * max(1, ((height >> level) + 3) // 4) * 8 for level in range(mips))
        assert len(dds) == 148 + count * stride
        header = bytearray(dds[:148]); struct.pack_into('<I', header, 140, 1)
        for name, index in mapping.items():
            assert 1 <= index <= count
            data = bytes(header) + dds[148 + (index - 1) * stride:148 + index * stride]
            images[name] = Image.open(io.BytesIO(data)).convert('RGBA').resize((64, 64), Image.Resampling.LANCZOS)
    columns = 32
    atlas = Image.new('RGBA', (columns * 64, math.ceil(len(images) / columns) * 64))
    icons = {}
    for index, (name, image) in enumerate(sorted(images.items())):
        x, y = index % columns * 64, index // columns * 64
        atlas.paste(image, (x, y)); icons[name] = dict(x=x, y=y, width=64, height=64)
    args.output.mkdir(parents=True, exist_ok=True)
    atlas.save(args.output / 'icons.webp', quality=90)
    manifest = dict(engineCommit=PIN, treeVersion='0_5', treeSha256=hashlib.sha256(tree_bytes).hexdigest(),
                    archiveSha256=hashlib.file_digest(args.archive.open('rb'), 'sha256').hexdigest(), icons=icons,
                    source='https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases/tag/v0.23.1')
    (args.output / 'manifest.json').write_text(json.dumps(manifest, separators=(',', ':')))
    (args.output / 'NOTICE.txt').write_text('Path of Exile 2 game artwork: Grinding Gear Games.\nExtracted from Path of Building Community PoE2 v0.23.1.\n' + (args.pob / 'LICENSE.md').read_text())
    print(json.dumps({'icons': len(icons), 'atlasBytes': (args.output / 'icons.webp').stat().st_size, 'engineCommit': PIN}))


if __name__ == '__main__': main()
