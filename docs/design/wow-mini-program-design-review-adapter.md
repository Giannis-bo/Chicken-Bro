# WoW Mini Program Design Review Adapter

> Purpose: adapt community "taste skill" style critique into this project's evidence-first WoW mini-program UI workflow. This document is a project-local review adapter, not an installed global Codex skill.

## Source Inputs

- External reference: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)
- Relevant ideas to adapt: design audit before redesign, visual taste dials, anti-generic-AI UI checks, and image generation as a design material workflow.
- Project constraints: [UI style guide](../ui-style-guide.md), [current spec workbench brief](../plans/2026-06-29-current-spec-workbench-product-brief.md), and [WoW app UI redesign plan](../plans/2026-06-30-wow-app-ui-redesign-plan.md).

## When To Use

Use this adapter before any UI implementation or imagegen round that touches:

- News home, channel lists, article cards, and first-screen information density.
- Builds / specialization tab and the "current spec workbench" entry.
- Current spec workbench readiness, blockers, module status, and evidence details.
- Talent simulator, gear simulator, SimC, task list, Chickenbro, and profile/template surfaces.
- Screenshot acceptance, especially official WeChat DevTools mini-program captures.

Do not use this adapter to justify fabricated data, fake WoW icons, DPS, rankings, grades, or "upgrade priority" labels.

## Taste Dials

These are fixed for this product unless the roadmap changes.

| Dial | Value | Meaning |
| --- | --- | --- |
| Density | High | First screen must show the object, state, reason, and next action. Avoid tall marketing heroes and empty vertical space. |
| Motion | Low | Motion is not a product pillar for this mini-program. Use native state changes, fixed action bars, sheets, and concise transitions. |
| Variance | Medium-high | Avoid every screen becoming the same card grid. Use different information shapes for news, readiness, trees, equipment, tasks, and chat. |
| Evidence strictness | Max | Never let visual polish weaken data trust. Status, icons, numbers, and labels must come from real read models or controlled fixtures. |
| WoW materiality | Medium | Use game icons, dark iron panels, gold borders, and subtle Warcraft-like material cues. Avoid heavy fantasy skins that reduce readability. |

## Non-Negotiables

- Complete SimC-ready talents + core gear are required before showing DPS, grades, rankings, upgrade priority, or comprehensive scores.
- Real WoW object icons must come from API/read-model fields such as `gameAsset.iconUrl` or another verified source. Imagegen must not invent class, spec, talent, item, source, or logo icons.
- `verified`, `partial`, `source_reference`, `blocked`, and `stale` must stay visually and semantically consistent with `docs/ui-style-guide.md`.
- Blocked states are not error pages. They must explain what is missing, why it matters, and where to go next.
- New-player mode gets conclusion + action. Advanced evidence lives behind expansion, lower-screen rows, or a secondary details view.
- A screenshot scene is not accepted just because it produced a PNG. The visible image must prove the named state.

## Screenshot Review Protocol

For each official mini-program screenshot:

1. Confirm route and scene name match the visible screen.
2. Confirm the image is not blank and not mostly uninformative dark space.
3. Identify the first-screen object: what is the user looking at?
4. Identify the current state: ready, blocked, partial, stale, source reference, empty, loading, or chat.
5. Identify the next action: is it visible, specific, and reachable?
6. Check evidence: does the screen show source, freshness, coverage, blocker, or template status when needed?
7. Check visual taste: is the layout app-like, dense, and topic-specific, or generic card stacking?
8. Check trust: are any labels, numbers, icons, or conclusions stronger than the evidence allows?

## Severity Model

| Severity | Definition | Examples |
| --- | --- | --- |
| P0 | Breaks the main product path, data trust, or screenshot acceptance. | Workbench sends spec to SimC but SimC does not inherit it; screenshot named "scrolled" is not actually scrolled; readiness count contradicts blocker. |
| P1 | Product is usable but information hierarchy, comprehension, or theme quality is materially weaker. | Repeated blocked messages, duplicate homepage content, evidence too far below the fold, generic module cards. |
| P2 | Polish issue or second-order taste issue. | Awkward labels, raw timestamps, overly similar border treatments, minor empty-space imbalance. |

## Anti-Generic UI Checks

Flag these whenever they appear:

- A grid of cards where each card has the same shape, same CTA, and only text differs.
- Hero and list repeat the same headline or status without adding decision value.
- Labels sound like scaffolding rather than product language, such as internal counters or unexplained "能力 02".
- Big empty vertical areas after a small amount of content.
- English system words leak into Chinese product UI, unless they are player-facing terms such as SimC or DPS.
- Decoration carries the page while the actual data hierarchy stays weak.
- Status color is doing the work that copy and hierarchy should do.

## Imagegen Material Workflow

Use imagegen only after product state and layout have been decided.

Allowed imagegen outputs:

- Subtle dark iron / parchment / arcane panel textures.
- Abstract status backgrounds for blocked, partial, ready, and source reference states.
- Non-literal atmospheric assets for empty states.
- Mood boards that test density, contrast, and material language.

Disallowed imagegen outputs:

- WoW class, spec, talent, item, boss, source, or faction icons.
- Fake screenshots treated as product truth.
- Text baked into UI assets.
- DPS, rankings, grades, scores, source badges, or blocker conclusions.

Imagegen handoff format:

```markdown
Object:
State:
Layout slot:
Allowed visual language:
Forbidden content:
Real assets required:
Implementation note:
```

## Review Output Template

Use this structure for screenshot CR:

```markdown
# <date> Official Screenshot UI CR

## Summary

- Baseline:
- Acceptance:
- Main verdict:

## P0

| Scene | Finding | Evidence | Impact | Fix |
| --- | --- | --- | --- | --- |

## P1

| Scene | Finding | Evidence | Impact | Fix |
| --- | --- | --- | --- | --- |

## P2

| Scene | Finding | Evidence | Fix |
| --- | --- | --- | --- |

## Next Implementation Pass

1.
2.
3.
```

## Done Criteria

The next UI pass is not complete until:

- Official mini-program screenshots cover every named scene and visually prove each scene.
- P0 findings are fixed or explicitly deferred by the user.
- All visible strong claims are backed by evidence.
- Real WoW icons are real assets, not generated placeholders.
- `node --test` regression and `git diff --check` pass.
