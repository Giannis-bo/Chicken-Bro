# Shared Chrome V1 Candidate Raster Assets

Status: `generated_pending_independent_isolated_review`

Source class: `imagegen_raster`

This directory contains candidate-only, non-factual shared page chrome. It is not registered in `packages/assets-manifest`, is not wired into runtime code, and makes no production or acceptance claim.

## Generation Summary

- Built-in `image_gen` calls: 4
- Iteration calls: 0
- Preserved built-in sources: 4
- Transparent masters: 4
- Runtime asset IDs: 5
- Runtime PNG files: 10
- Transparency method: installed `remove_chroma_key.py` helper with border auto-key, soft matte, despill, and no model-native transparency fallback
- Mechanical derivation: centered `sips` crop/resize; 1x files derive from 2x; the right title rail is a horizontal `sips` mirror of the left title rail at the same density

The title ornament uses one generated source and one transparent master for both runtime slots. `title-ornament-family.right-rail` is mechanical mirror output, not a fifth generation.

## Built-In Sources And Masters

| Generation | Built-in saved path | Workspace source | Transparent master |
| --- | --- | --- | --- |
| `shared-page-corner.default` | `/Users/heyesheng/.codex/generated_images/019f6396-3539-7681-bd52-af5f1a3e35ff/exec-7a66d396-e240-46e0-b682-d387a6de1961.png` | `sources/shared-page-corner.default.png`, 1254x1254, 1770255 bytes, `c8ccff397d218cb94cd7cc2463ad8aa230be7fdbeafbfaf984f1d100216d7f4b` | `masters/shared-page-corner.default.png`, 1254x1254, 1217258 bytes, `e60265553205f2320bacfc21976de14ce5d6b2aaac80e4a1af8c03e2db732b34` |
| `shared-page-side-rail.default` | `/Users/heyesheng/.codex/generated_images/019f6396-3539-7681-bd52-af5f1a3e35ff/exec-c60e6b66-2ca3-4f45-a270-46e08fb0ef6d.png` | `sources/shared-page-side-rail.default.png`, 793x1983, 1317674 bytes, `d7b58305bfd13042534448fd79a78918533849659540e7516bb59ba64f778dab` | `masters/shared-page-side-rail.default.png`, 793x1983, 630987 bytes, `a4b8aa7c4021f76d1a1e5fa558effd5a9e0409622ed1f7bcaae1e8df0b1b5e99` |
| `title-ornament-family.rail-source` | `/Users/heyesheng/.codex/generated_images/019f6396-3539-7681-bd52-af5f1a3e35ff/exec-eee2cf73-554e-46c0-ba8a-296e9c6a2e79.png` | `sources/title-ornament-family.left-rail.png`, 1983x793, 1347809 bytes, `db9ab541dbb6c383b7d0840ac09f5e2cad1a59d7918ce0aa3266787ccc4984bb` | `masters/title-ornament-family.left-rail.png`, 1983x793, 636883 bytes, `7906e6268b35ecb92d5f2a02a925785c9ec1fef96c1c5fc4489b384dc6031c96` |
| `pushed-back-medallion.default` | `/Users/heyesheng/.codex/generated_images/019f6396-3539-7681-bd52-af5f1a3e35ff/exec-ecfeecd1-35d8-4c3b-980d-cc2cb8321417.png` | `sources/pushed-back-medallion.default.png`, 1254x1254, 1670789 bytes, `baa658e170570102d94697f9be2bbc7c563fe8d7c433c532a6f297214979121a` | `masters/pushed-back-medallion.default.png`, 1254x1254, 1053241 bytes, `42153b09c1ccfc18b15e4e2a744b8ee6eb546b00033a559bcfaa4c98bb783542` |

## Runtime Outputs

| Asset ID | 2x | 1x | Derivation |
| --- | --- | --- | --- |
| `shared-page-corner.default` | `runtime/2x/shared-page-corner.default.png`, 112x112, 10219 bytes, `941e68f2e930a4f9565d3313c0928dd9e6df4ed0fa1e2f9b971beb76f6c59623` | `runtime/1x/shared-page-corner.default.png`, 56x56, 3439 bytes, `a6f0d0e991aa93db346dffd76e61e4b8e5029a2cdef91ceb6429e4f4526293ba` | Square master resize; 1x from 2x |
| `shared-page-side-rail.default` | `runtime/2x/shared-page-side-rail.default.png`, 24x256, 10618 bytes, `0c7fc3ed36fcc1fdf92c0d439e454f860a29ced02c7e952b7ef2a9cad847ea52` | `runtime/1x/shared-page-side-rail.default.png`, 12x128, 3489 bytes, `3e7dc1ab370fac736e8fda5ce543e402fc05a98d5d890f8e331948b6869f234f` | Centered 1983x186 crop, resize; 1x from 2x |
| `title-ornament-family.left-rail` | `runtime/2x/title-ornament-family.left-rail.png`, 192x40, 6874 bytes, `175132c52186159049ca38d05d0266616e18f57644b97838e0cc13b562cfa561` | `runtime/1x/title-ornament-family.left-rail.png`, 96x20, 2601 bytes, `4207e0743e8dd3857da7dc88ba5f966b4a309ae5c0f0442abc9be6f4e2a66d24` | Centered 413x1983 crop, resize; 1x from 2x |
| `title-ornament-family.right-rail` | `runtime/2x/title-ornament-family.right-rail.png`, 192x40, 7019 bytes, `21143b4f415ed725d6e8de601b480bc3a747c89c6dd32189d1003389d0909643` | `runtime/1x/title-ornament-family.right-rail.png`, 96x20, 2574 bytes, `04aa5deff9bd5674360c0a63535b623d490daa2fd7e3847d2c7f6ea8cdcdcbcd` | Exact horizontal mirror of left runtime; mirror AE is 0 at both densities |
| `pushed-back-medallion.default` | `runtime/2x/pushed-back-medallion.default.png`, 88x88, 8522 bytes, `69b7692cfbd0163dab2568141e4f50577737b6ba2e8cb80d4e59d1ddd14aa100` | `runtime/1x/pushed-back-medallion.default.png`, 44x44, 3401 bytes, `c5314c6d3065ba11db78535895c802750bb7e3c800a05512142b530ac6c77c04` | Square master resize; 1x from 2x |

## Mechanical Validation

All 10 runtime PNGs passed the recorded mechanical checks:

- Exact requested dimensions and RGBA channels
- Four transparent corner pixels per file
- Non-transparent coverage between 0.312371 and 0.833333
- Zero visible green-fringe fraction under the recorded alpha-aware threshold
- Empty Tesseract OCR output for text and digits
- Empty medallion center with alpha maximum 0 in the central validation area
- Exact left/right title mirror with 0 absolute-error pixels
- Side-rail top/bottom normalized alpha RMSE at or below 0.00506272 and color RMSE at or below 0.0294538

Detailed prompts, commands, per-file metadata, chroma-key statistics, and validation values are in `generation-record.json` and `manifest.json`.

## Pending Review

Independent isolated visual review remains required for route-level material fit, perceived weight at final scale, title-slot composition, medallion/icon layering, and visible repeat-y behavior in the actual page compositor. Mechanical validation does not promote these candidates or establish production acceptance.
