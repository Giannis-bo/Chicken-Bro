# News List V1 Candidate Raster Assets

Status: `independent_review_passed_for_canary`

Source class: `imagegen_raster`

Production promoted: `false`

This directory contains two candidate-only, non-factual raster assets for `news_list`. Both passed one-asset-per-context isolated review, are registered as non-production canary candidates, and are wired into the route owner. This does not grant route visual acceptance or production promotion.

## Generation Summary

- Built-in `image_gen` calls: 2
- Iteration calls: 0
- Preserved built-in sources: 2
- Transparent masters: 2
- Runtime asset IDs: 2
- Runtime PNG files: 4
- Input target/runtime images read: 0
- Transparency method: installed `remove_chroma_key.py` helper with border auto-key, soft matte, despill, and no model-native transparency fallback
- Mechanical derivation: centered crop only for the portrait document source, then `sips` resize; every 1x file derives from its 2x file

## Built-In Sources And Masters

| Asset ID | Built-in saved path | Workspace source | Transparent master |
| --- | --- | --- | --- |
| `news-list-document-medallion.default` | `/Users/heyesheng/.codex/generated_images/019f63e1-cb5f-7d63-9fb7-031d5ca16b32/exec-88ccb026-a0bc-4fb9-8836-57dfb07c0e49.png` | `sources/news-list-document-medallion.default.png`, 1199x1312, 1926560 bytes, `9aea17ad76377ff72fd54d67f14b4ad58a3d598e450fc1920f22da842689937f` | `masters/news-list-document-medallion.default.png`, 1199x1312, 1568970 bytes, `860ec5c6bd874505895085d0a554531d7bc3f875ca61e7353b4eae755f5b78e4` |
| `news-list-terminal-medallion.default` | `/Users/heyesheng/.codex/generated_images/019f63e1-cb5f-7d63-9fb7-031d5ca16b32/exec-29111be2-1f50-4f8f-a14d-1923ffdebea1.png` | `sources/news-list-terminal-medallion.default.png`, 1254x1254, 2154771 bytes, `ef0eedc1d5a2ebd8928e17e254667e2c3b1eaf84dc10aa83dac8eaf6133d5243` | `masters/news-list-terminal-medallion.default.png`, 1254x1254, 1631694 bytes, `d10427eeadbc97088d2a5c1320969bc0b4e30410c1a8a5438902fe4ab248f6a6` |

## Runtime Outputs

| Asset ID | 2x | 1x | Derivation |
| --- | --- | --- | --- |
| `news-list-document-medallion.default` | `runtime/2x/news-list-document-medallion.default.png`, 84x92, 9613 bytes, `bf8a6a5dcf6001a9e7088aa265bc5388b82ba7b973cd6fbe05adec05f05e2152` | `runtime/1x/news-list-document-medallion.default.png`, 42x46, 3199 bytes, `c5f16fa079d529e3ac23bf7d5d12c1f904fd1a2cd5aa1640d5e0f78b285b3c45` | Centered 1312x1198 crop, resize to 2x; 1x from 2x |
| `news-list-terminal-medallion.default` | `runtime/2x/news-list-terminal-medallion.default.png`, 112x112, 15328 bytes, `9d286790d4fd4b4060cf4c50929b8f3f74bc758e6f953d5c442e14219372eb9e` | `runtime/1x/news-list-terminal-medallion.default.png`, 56x56, 5388 bytes, `61ef5dca58f5158dc6b62f386ace1f1a905548f809031d91ddd89eb9e3263646` | Square master resize to 2x; 1x from 2x |

## Mechanical Validation

All four runtime PNGs passed the recorded checks:

- Exact requested dimensions and RGBA channels
- Four transparent corner pixels and fully transparent outermost edges
- Mean alpha coverage between 0.385315 and 0.461802
- Zero visible green-fringe fraction under the recorded alpha-aware threshold
- Empty Tesseract OCR output for text and digits
- Fully opaque central document validation area at both densities
- Fully transparent terminal center validation area at both densities
- Both 1x files are byte-identical to fresh `sips` re-derivations from their 2x files
- Both workspace source files are byte-identical to the built-in saved outputs

Detailed prompts, built-in call results, processing commands, per-file metadata, chroma-key statistics, and validation values are in `generation-record.json` and `manifest.json`.

## Independent Review

Both assets passed independent isolated review for canary integration. See `reviews/document-medallion.json`, `reviews/terminal-medallion.json`, and `independent-review.json`. The terminal review records a non-blocking concern about dense outer-ring detail and a slightly strong top highlight at 56x56. Mechanical and isolated review do not promote these candidates to production or establish route acceptance.
