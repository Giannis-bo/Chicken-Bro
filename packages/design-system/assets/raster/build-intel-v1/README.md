# Build Intel V1 Candidate Raster Assets

Status: `candidate_pending_runtime_review`

Source class: `imagegen_raster`

Fact-bearing: `false`

Production promoted: `false`

This directory contains three candidate-only, non-factual decorative raster assets for `build_intel`. Each asset passed one-at-a-time isolated static review and deterministic alpha validation. Runtime composition, route fidelity, H5 behavior, WeChat behavior, and production promotion remain pending.

The collection is not registered in `packages/assets-manifest`, is not wired into runtime code, and does not grant route visual acceptance.

## Generation Summary

- Built-in `image_gen` calls: 3
- CLI or direct API image-generation calls: 0
- Iteration calls: 0
- Preserved built-in sources: 3
- Transparent masters: 3
- Runtime asset IDs: 3
- Runtime PNG files: 6
- Input target images read: 0
- Input route-runtime images read: 0
- Transparency method: installed `remove_chroma_key.py` helper with border auto-key, soft matte, despill, and no model-native transparency fallback
- Mechanical derivation: ImageMagick alpha-bounds trim, proportional fit, centered transparent extent to 2x, then deterministic `sips` resize from 2x to 1x
- Review mode: one generated candidate at a time in the disposable isolated context; no image payload returned to the main project session

## Built-In Sources And Masters

| Asset ID | Slot ID | Built-in saved path | Workspace source | Transparent master |
| --- | --- | --- | --- | --- |
| `build-intel-summary-medallion.default` | `asset_slot.build-intel-summary-medallion` | `local-generation-output-not-retained` | `sources/build-intel-summary-medallion.default.png`, 1254x1254, 2698074 bytes, `7b25b90fb3d022263143530d99b4933f0e0a7c60fea9e1fde766a064f1155060` | `masters/build-intel-summary-medallion.default.png`, 1254x1254, 2484208 bytes, `15cf3d03d78fb6ff9dc5cbda457930450a77f0e8a309a87626f14519cc1c3e58` |
| `build-intel-card-medallion-shell.default` | `asset_slot.build-intel-card-medallion-shell` | `local-generation-output-not-retained` | `sources/build-intel-card-medallion-shell.default.png`, 1254x1254, 2046577 bytes, `e36778596f5460d73ec470255e86a0a9526bc353fd2efdbf21983c9092f08c78` | `masters/build-intel-card-medallion-shell.default.png`, 1254x1254, 1519215 bytes, `7e873bd4de7e802317a727061a5c78709fd05ab0701147b9123be99690fff19b` |
| `build-intel-primary-action.default` | `asset_slot.build-intel-primary-action` | `local-generation-output-not-retained` | `sources/build-intel-primary-action.default.png`, 1915x821, 1701373 bytes, `282dbbc2d779e5e5255c291f106520e538de2967adb1e793228336a33f40ea72` | `masters/build-intel-primary-action.default.png`, 1915x821, 1488286 bytes, `476108f8a8b30b920294342e3e3f7e7d220994e9d334d7d5cdb392f2e3896ce9` |

Every workspace source is byte-identical to its built-in saved output.

## Runtime Outputs

| Asset ID | Intended CSS optical box | 2x | 1x | Derivation |
| --- | --- | --- | --- | --- |
| `build-intel-summary-medallion.default` | 92x92 | `runtime/2x/build-intel-summary-medallion.default.png`, 256x256, 97954 bytes, `72413f6c78ebecd144622fcddb23b5e19aaef8b65f55290ef945d1a8ed8a5c3b` | `runtime/1x/build-intel-summary-medallion.default.png`, 128x128, 27361 bytes, `bef5f07ea7ed629017c4742d623be5b7cc3617f59d641c6c3175ada5fa0d6a6f` | Alpha trim, fit within 240x240, center on 256x256; 1x from 2x |
| `build-intel-card-medallion-shell.default` | 68x68 | `runtime/2x/build-intel-card-medallion-shell.default.png`, 192x192, 44601 bytes, `d96b363f94f487b948ec3255f0aca2a13fa69276d801048f801ae1a1026f714a` | `runtime/1x/build-intel-card-medallion-shell.default.png`, 96x96, 12899 bytes, `84faae69a596d17b29328c49fb78d4cc483382a7f114f873f75b9d8d8786ebe1` | Alpha trim, fit within 184x184, center on 192x192; 1x from 2x |
| `build-intel-primary-action.default` | approximately 84x36 | `runtime/2x/build-intel-primary-action.default.png`, 336x144, 43744 bytes, `a6529ec2484dca51816ce7da2d40aa71eb90b6530364e4ed5fbb811d5947a813` | `runtime/1x/build-intel-primary-action.default.png`, 168x72, 13848 bytes, `e8cfcd62a132cc1430f46f911349e6c9dbd766aa4fa9036bf4c6848fa5d1c1a3` | Alpha trim, fit within 328x136, center on 336x144; 1x from 2x |

## Mechanical Validation

All six runtime PNGs passed the recorded checks:

- Exact requested dimensions and RGBA channels
- Four zero-alpha corner pixels and fully zero-alpha outermost edges
- Mean alpha coverage from 0.392874 to 0.59688
- Zero visible green-fringe fraction under the recorded alpha-aware threshold
- Empty Tesseract OCR output for text and digits
- Fully opaque summary-medallion center at both densities
- Fully transparent card-shell center at both densities
- Fully opaque primary-action overlay area at both densities
- Every 1x file is byte-identical to a fresh `sips` re-derivation from its 2x file
- Every source file is byte-identical to the corresponding built-in saved output

Detailed prompts, built-in saved paths, processing commands, per-file metadata, chroma-key statistics, and validation values are in `generation-record.json` and `manifest.json`.

## One-Asset Static Review

| Asset ID | Static conclusion | Remaining runtime review |
| --- | --- | --- |
| `build-intel-summary-medallion.default` | Pass: centered face-on silhouette; readable bronze/dark-iron shell hierarchy; distinct opaque center socket; generic compass and blank-scroll semantics; no prohibited factual or identity content | Confirm scale, visual weight, and adjacent-content competition in the 92x92 summary composition |
| `build-intel-card-medallion-shell.default` | Pass: neutral ring-only housing; clean large transparent aperture; no baked-in media, glyph, or factual content | Confirm trusted specialization media and neutral fallback clearance, contrast, and alignment in BuildIntelCard |
| `build-intel-primary-action.default` | Pass: clipped bronze-gold plate; calm fully opaque center; clear glyph-plus-label overlay area; no baked-in text or factual content | Confirm label fit, glyph contrast, pressed and disabled states, and card alignment at approximately 84x36 CSS |

See `reviews/summary-medallion.json`, `reviews/card-medallion-shell.json`, `reviews/primary-action.json`, and `independent-review.json` for structured findings.

## Promotion Boundary

All assets remain `candidate_pending_runtime_review`. Static review and mechanical validation do not prove target fidelity, runtime acceptance, H5 verification, WeChat verification, route acceptance, or release readiness. No registry, component, route, documentation control plane, or other path was modified by this package task.
