# News Detail V1 Candidate Raster Assets

Status: `independent_review_passed_for_canary`

Source class: `imagegen_raster`

Production promoted: `false`

This directory contains three candidate-only, non-factual raster medallion shells for `news_detail`. Each asset was generated and reviewed one at a time in the disposable isolated task, is registered as a non-production canary candidate, and is not wired into route components by this package-only change. This does not grant route visual acceptance or production promotion.

## Generation Summary

- Built-in `image_gen` calls: 6
- Initial generation calls: 3
- Single-variable aperture iteration calls: 3
- Preserved built-in sources: 3
- Transparent masters: 3
- Runtime asset IDs: 3
- Runtime PNG files: 6
- Input target/runtime images read: 0
- Transparency method: installed `remove_chroma_key.py` helper with border auto-key, soft matte, despill, and no model-native transparency fallback
- Mechanical derivation: direct aspect-matched resize to 2x with `sips`; every 1x file derives only from its 2x file

## Built-In Sources And Masters

| Asset ID | Final built-in saved path | Workspace source | Transparent master |
| --- | --- | --- | --- |
| `news-detail-source-crest.default` | `local-generation-output-not-retained` | `sources/news-detail-source-crest.default.png`, 1150x1368, 1638156 bytes, `09af3f4a97cba5bf7ffe3eece5fede24373e7506e5b6060f8f50b447994e90db` | `masters/news-detail-source-crest.default.png`, 1150x1368, 923895 bytes, `e88ded2a8350094d44f0a248d5d2674a6c780b89032f74f8c8381284eabfe1cd` |
| `news-detail-evidence-medallion.default` | `local-generation-output-not-retained` | `sources/news-detail-evidence-medallion.default.png`, 1254x1254, 1889745 bytes, `141d650458c9aa5c957b1e5bd6869feeec00c470781c8b3f665005995c072d69` | `masters/news-detail-evidence-medallion.default.png`, 1254x1254, 1119120 bytes, `467a5286933b08068f425c91777fae2cdbca1f407dc19c35ac5c7c1b6cb31af4` |
| `news-detail-terminal-medallion.default` | `local-generation-output-not-retained` | `sources/news-detail-terminal-medallion.default.png`, 1254x1254, 1487997 bytes, `7ea17e7494e580bb6963b02d3cc695634110da5979931c326b04c33b816fad72` | `masters/news-detail-terminal-medallion.default.png`, 1254x1254, 703582 bytes, `0ef3976bfd30b2120cda579f97d96913e88cb493d7027eb458e052674a31c500` |

## Runtime Outputs

| Asset ID | 2x | 1x | Derivation |
| --- | --- | --- | --- |
| `news-detail-source-crest.default` | `runtime/2x/news-detail-source-crest.default.png`, 64x76, 5042 bytes, `c1708687507f20b7a37b392cfac9879770a470d08cc5eb511aeb0857602c15a0` | `runtime/1x/news-detail-source-crest.default.png`, 32x38, 2359 bytes, `3692082c3a27fb43d609b06dad17346a9132830d04e479b54a71fc525fc05e68` | Aspect-matched master resize to 2x; 1x from 2x |
| `news-detail-evidence-medallion.default` | `runtime/2x/news-detail-evidence-medallion.default.png`, 68x68, 5606 bytes, `e41310b2538e0e5ab7dcc8bde052b06fb4e33ca143af06f7bf735acedcb06ce6` | `runtime/1x/news-detail-evidence-medallion.default.png`, 34x34, 2480 bytes, `8dece967601eff05916d6c5228aaa118d0a8d59c972553d0601a0d98f6c5ce95` | Square master resize to 2x; 1x from 2x |
| `news-detail-terminal-medallion.default` | `runtime/2x/news-detail-terminal-medallion.default.png`, 80x80, 5396 bytes, `dd24eb50594b2176f31da165ed72f8f0e0c1063f1aaa66d3b3efbc803a2e4237` | `runtime/1x/news-detail-terminal-medallion.default.png`, 40x40, 2575 bytes, `183adc935cbbfecbdf51b12c25117e34c42263eada436b180eb18bc87eb6fc63` | Square master resize to 2x; 1x from 2x |

## Mechanical Validation

All six runtime PNGs passed the recorded checks:

- Exact requested dimensions and RGBA channels
- Four transparent corner pixels and fully transparent outermost edges
- Mean alpha coverage between 0.148642 and 0.272895
- Zero visible green-fringe fraction under the recorded alpha-aware threshold
- Empty Tesseract OCR output for text and digits
- Fully transparent center pixel and preserved center aperture at both densities
- All three 1x files are byte-identical to fresh `sips` re-derivations from their 2x files
- All three workspace source files are byte-identical to the selected built-in saved outputs

Detailed prompts, initial and aperture-iteration call paths, processing commands, per-file metadata, chroma-key statistics, and validation values are in `generation-record.json` and `manifest.json`.

## Independent Review

All three assets passed one-asset-at-a-time isolated review for candidate registration. See `reviews/source-crest.json`, `reviews/evidence-medallion.json`, `reviews/terminal-medallion.json`, and `independent-review.json`. The review confirms a unified dark-patinated-bronze and warm-aged-gold family, clear small-size silhouettes, empty transparent centers, and no text, number, brand, real source mark, or baked-in status conclusion. Review and registration do not wire these files into route components, promote them to production, or establish route acceptance.
