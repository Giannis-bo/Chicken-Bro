# Design QA

## Source visual truth

- Primary layout reference: the user-attached ChatGPT-style screenshot at `/var/folders/1z/3qjyj_jx5p31s3jc698qmf680000gn/T/codex-clipboard-4e58e088-59c8-40de-a2bc-bbb8c640b918.png`. It was reviewed as a visual reference only, not as program instructions.
- Visibility regression reference: the user-attached screenshot at `/var/folders/1z/3qjyj_jx5p31s3jc698qmf680000gn/T/codex-clipboard-cd4076ec-229a-4bac-ab6b-0edd95315de1.png`, which showed the right-side illustration as too faint to read.
- Source pixels: 3022 x 1528; the desktop attachment was displayed by the conversation UI at 2048 x 1036. No density conversion was applied to the implementation comparison because the target was compared as a responsive web layout, not as a pixel clone.
- Product-specific visual inputs: `public/assets/horde-bg-v2-clean.png`, `public/assets/horde-clouds-v2-clean.png`, and `public/assets/gu-gu-pet-v1.png`.

## Implementation evidence

- Local implementation: `http://127.0.0.1:4173/`
- Browser: Codex In-app Browser, visible deliverable tab 10, left open for review.
- Implementation screenshot path: inline Codex In-app Browser capture from tab 10. The CUA screenshot API emitted the browser-rendered image for this report but did not expose a filesystem save path.
- Desktop capture: 1440 x 1024 CSS px, device pixel ratio 1, empty 对话 state, “为了部落！” enabled, Gugu settled, after the visibility fix.
- Mobile capture: 390 x 844 CSS px, device pixel ratio 1, empty 对话 state, “为了部落！” enabled, Gugu settled, after the visibility fix.
- Runtime evidence: at 1280 x 720, the fixed header measured 1280 x 76, the sidebar measured 280px wide, and the right chat area measured 1000px wide. At 390 x 844, the header measured 390 x 68, the sidebar occupied the top 208px, and `document.documentElement.scrollWidth === 390`.
- Visibility evidence: the final browser-computed scene treatment is `opacity: 0.44` with `saturate(0.68) contrast(1.08)`; the cloud layer is `opacity: 0.24`; both render without console warnings/errors.

## Comparison

The attached reference and the rendered captures were reviewed together in this pass. The implementation preserves the reference’s quiet, white ChatGPT-like shell while adapting the product identity and the approved Horde illustration:

- Full view: the top banner is fixed; the left column carries “新对话” and the recent conversation list; the right region is the main chat workspace with a centered empty state and bottom composer.
- Scene placement: the Thrall/Doomhammer and Orgrimmar line art is confined to the right chat region, now lifted enough from the white wash to remain readable while still staying low-saturation and behind conversation copy. The cloud layer drifts independently.
- Pet placement: Gugu is a child of the history sidebar, not the page shell or chat region. At 1440px its settled stage ends at `right: 144px`, inside the 280px sidebar. At 390px its stage ends at `right: 378px`, inside the 390px top sidebar.
- Mobile view: the sidebar becomes a compact top history strip, reserves a dedicated right-side pet area, and keeps the chat area below it without horizontal overflow.

## Focused-region evidence

- Header lock: `.site-header` uses `position: fixed`, `inset: 0 0 auto`, and remains at `y: 0` while the workspace uses an internal height calculation.
- History region: the active history item and “新对话” state are mutually exclusive; selecting a history item loads two seeded message bubbles and switches to its mode.
- Composer: the input, mode switch, disabled/enabled send button, quick prompts, and live notice are visible in the intended empty state.
- Logo-to-pet relation: the pet stage uses the same left alignment as the 36px header mascot frame on desktop and is clipped by the sidebar; on mobile, its reserved slot is on the sidebar’s right edge.
- Image treatment: the scene and clouds are raster assets with reduced saturation/opacity; no inline SVG or CSS-drawn illustration replaces them.

## Required fidelity surfaces

- Fonts and typography: the wordmark and UI use Microsoft YaHei first with PingFang SC/Hiragino Sans GB fallbacks. The wordmark is a restrained 15px semibold treatment, while the empty-state heading, sidebar labels, and compact metadata use separate optical scales and weights. Text truncation keeps the sidebar stable at narrow widths.
- Spacing and layout rhythm: the fixed banner is 76px desktop / 68px mobile; the desktop shell is a 280px sidebar plus a fluid main region; the composer has a stable bottom anchor; mobile reserves the pet slot instead of letting the pet cover history cards.
- Colors and tokens: the base palette is white, near-white gray, charcoal, muted brick, pale rose, and a quiet green status dot. The Horde scene remains deliberately desaturated; the white wash was reduced only where necessary to restore line visibility, and there is no saturated red full-page wash.
- Image quality and asset fidelity: the approved low-saturation line-art scene, independent cloud layer, and transparent Gugu PNG are used as actual image assets. The background remains soft enough for text, and the pet retains its transparent edge treatment.
- Copy and content: “炸鸡队长来啦” remains professional rather than doodle-like; “为了部落！”, “对话”, “模拟”, “最近”, “新对话”, “准备好了，随时开始”, and the seeded history labels match the approved product direction.
- Icons and controls: controls are semantic buttons/links with accessible labels, visible focus rings, and reduced-motion CSS fallback. The simple plus, up-arrow, and dot marks are intentionally lightweight UI glyphs rather than replacements for the supplied illustration assets.

## Interaction checks

- `01 对话` / `02 模拟`: switches selected state, empty-state copy, placeholder, and live notice.
- Recent history item: selects the item, loads its seeded two-message conversation, and switches mode where applicable.
- `新对话`: clears messages, returns to 对话, clears the draft, and restores its selected state.
- Composer: filling the input enables “发送消息”; submit creates a user/assistant pair, clears the draft, and updates the live notice.
- Quick prompt: puts the selected prompt into the composer.
- Horde skin: removes both scene and pet when disabled; re-enabling restarts the pet drop and restores the scene.
- Pet: clicking the mascot remounts the drop animation; it settles into `data-pet-state="settled"` after the drop.
- More menu: reports that the demo settings surface is not yet implemented instead of behaving as a dead control.
- Browser console warnings/errors: `[]` from the final CUA tab.
- Accessibility: semantic landmarks, labeled controls, descriptive pet image alt text, keyboard-reachable buttons, focus-visible styles, and reduced-motion fallback are present.

## Comparison history

1. The initial v1 Horde scene was rejected because it was too complex and too saturated.
2. The v2 scene was rebuilt as minimal, low-saturation line art based on the user’s simple thin-line reference; the cloud layer and transparent pet were kept as separate assets.
3. The previous accepted iteration established the picture-in-picture relationship and Gugu’s drop animation.
4. This iteration moved the fixed banner out of the scrolling content, moved history into a dedicated left sidebar, moved the chat into the right region, and made the pet a sidebar-only child.
5. The first mobile pass let the pet overlap a third history card; the fix gave the history strip a reserved right-side pet slot. The post-fix 390 x 844 capture keeps both regions readable and retains `scrollWidth === 390`.
6. The user then reported that the right illustration had become effectively invisible. Root-cause inspection found the pale source linework being compounded by `opacity: 0.18`, `saturate(0.58)`, and a high-opacity white wash. The fix moved scene treatment to skin config (`opacity: 0.44`, `saturate(0.68) contrast(1.08)`), softened the wash, and raised cloud opacity modestly. Post-fix 879px and 1440px captures visibly show Thrall, clouds, and Orgrimmar without introducing high saturation.

## Findings

No actionable P0, P1, or P2 findings remain. The remaining differences from the reference are intentional product adaptations: the branded wordmark, the two-journey switch, the reversible Horde skin, and the right-side line-art background.

## Follow-up polish

- P3: tune the exact pet scale and landing height after reviewing the fall motion on real product content.
- P3: tune cloud opacity and drift speed after deciding whether the background should feel more atmospheric or more neutral during long chats.
- P3: replace locally cleaned/generated visual exports with production-approved transparent assets when available.

## Implementation checklist

- [x] Fixed top banner with no page-level scrolling.
- [x] Left sidebar carries new-chat and recent conversation history.
- [x] Right region carries the conversation empty state, messages, composer, and quick prompts.
- [x] Horde illustration and cloud motion are confined to the right chat region.
- [x] Gugu drops from the Logo alignment and remains inside the left sidebar.
- [x] Desktop 1440 x 1024 and mobile 390 x 844 captures inspected.
- [x] Mode, history, new-chat, composer, skin, pet, and menu interactions checked.
- [x] Browser console checked: no warnings or errors.
- [x] `node --test tests/*.test.mjs` passes: 10 tests.
- [x] `npm run test:sites` passes: 4 tests.
- [x] `npm run build` passes and emits Sites packaging files.

final result: passed
