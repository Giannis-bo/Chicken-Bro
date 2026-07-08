# TalentTreeCanvas Component Precheck

Status: `surface_component_precheck`
Created: 2026-07-07

## Scope

This precheck renders `TalentTreeCanvas` fixture states with production WXSS class names in local headless Chrome. It does not touch WeChat DevTools and does not connect the owner to `pages/builds/talent-simulator`.

## Evidence

- Manifest: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/manifest.json`
- Fixture HTML: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-fixture.html`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crop-contact-sheet.png`
- Viewports: `compact / standard / large`
- Crops: `8`
- Failures: `0`
- Warnings: `0`

## Measured Invariants

- Owner rect exists across compact, standard and large viewports.
- Document has no horizontal overflow.
- Tree shell exists for every fixture.
- Node rects stay inside the tree shell.
- Choice node affordance, rank badge, icon socket and node base are cropped as one owner component.
- No visible DPS, score, tier, ranking, upgrade-priority, fake host chrome or raw secret-like text is present.

## Crops

- talent-tree-ready-surface: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-ready-surface.png`
- talent-tree-header: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-header.png`
- talent-tree-viewport: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-viewport.png`
- talent-tree-choice-node: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-choice-node.png`
- talent-tree-locked-path: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-locked-path.png`
- talent-tree-action-rail: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-action-rail.png`
- talent-tree-evidence: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-evidence.png`
- talent-tree-missing-icon: `artifacts/ui-system-rebuild/20260707-talent-tree-canvas-component-precheck/component-crops/talent-tree-missing-icon.png`

## Non-Promotion

This evidence is only `surface_component_precheck`. It cannot authorize page edits, cannot replace real WeChat mini-program screenshots and cannot prove final acceptance.
