# Community Template Fidelity Design

**Date:** 2026-07-16

**Status:** user-approved design; implementation plan not yet written

**Supersedes:** [Community Template Import Performance Design](2026-07-15-community-template-import-performance-design.md) only for the import result's fidelity, evidence-completeness and saved-template replay semantics. Its one-request, scoped immutable read and lazy slot-edit principles remain in force. [Community Enhancement Editability v2](2026-07-14-community-enhancement-editability-v2-design.md) remains the authority for canonical editability and evidence-derived enhancement constraints.

**Current roadmap contract:** [社区装备模板全量原样导入合同](../../roadmap.md).

## 1. User promise and current defect

A player imports a community template to see the observed target player's actual build, not an approximation: every required equipment slot, its exact item level and image, and the target's gems, enchants and embellishments. The player may subsequently edit those canonical selections within the verified capacity, but the initial imported facts must not be invented, averaged, or replaced by a generic catalog row.

The confirmed defect violates that promise. `server/community_template_import.py` first projects the selected exact variant's `itemLevel`, then overwrites it with the generic `websim_gear_release_items.item_level` when a generic item row exists. The generic value is the source of the displayed `197`; it is not the target player's item level. The same projection does not forward image metadata. `pages/builds/detail.js` then prioritizes this imported level over a matching candidate, while the slot card can only render an image supplied as `iconUrl`.

The resolver's aggregate `292.4` and the card-level `197` can therefore coexist. The former is a resolved snapshot; the latter is a corrupted display projection. They must never be treated as interchangeable facts.

## 2. Product contract

### 2.1 Exact import

For every required slot of an eligible `raiderio_observed_profile` winner, the import service must prove one immutable observed selection:

```text
slot + itemId + variantKey + observedItemLevel + observed enhancements
```

`observedItemLevel` is a source fact. It is not calculated from an average, inferred from a generic item row, substituted from a default track, or supplied by the mini-program. The exact selected Variant must agree with that level. The generic release item may provide verified presentation metadata such as localized name and image, but it is never an authority for the selected instance's level or variant identity.

The service must also prove an image for the exact selected item identity. An image is presentation metadata rather than a second player fact, but this product contract requires it to be complete: an import with a missing or unverified image cannot claim a complete player configuration.

This gate is about sealed image metadata, not a browser/CDN availability test. Once a verified `iconUrl` has been supplied, a transient client image-load failure may use the existing visual fallback or retry behavior, but it must not change the imported item identity, level, enhancement state or verified import result.

### 2.2 Enhancements and capacity

The target's selected gems, enchants and embellishments are facts until they reconcile one-to-one with a visible, verified, slot-applicable canonical option in the same Active Manifest. Reconciliation preserves gem occurrence order and duplicates.

The editable constraints are separate facts. Socket count and enhancement eligibility come only from the exact selected item/variant capability evidence and the release's global rules. The client never derives a maximum from selected-count, fixed display totals, a generic item row, or raw option tokens.

### 2.3 Atomic success or explicit block

The import endpoint has only two user-facing outcomes:

- `verified`: all required slots, display metadata, observed levels, selected enhancements and capacity evidence have been reconciled, and the existing Resolver returns the matching canonical result.
- `blocked`: one or more required proofs are absent, contradictory or inapplicable. Nothing is applied; the prior verified workbench remains visible.

`partial` is no longer a successful import state. A bounded problem list may identify the affected slots and categories, but it must not expose raw upstream values or silently apply the remaining slots.

The player-facing recovery copy is plain: “该社区模板的装备证据不完整，暂不能导入。请稍后重试或选择其他模板。” It does not mention Releases, Manifests or canonical IDs.

## 3. Data and ownership design

### 3.1 Versioned observed selection source

New Community Releases retain the existing resolver-facing `selection-intent-v1`, and publish a separate sealed `importEvidence` object in the Community Release payload. Its schema is `community-template-import-evidence-v1`; each slot carries `itemId`, `variantKey`, `observedItemLevel` and verified image metadata, while the object carries a bounded source fingerprint bound to the template's profile/gear identity and authored release revisions. The projector combines this server-only evidence with the v1 canonical enhancement selection before Resolver handoff.

If source ingestion cannot preserve `observedItemLevel` for a slot, that template may remain browsable as historical evidence but is not importable. Request-time code must not reconstruct the missing fact from generic catalog metadata. The required fact is materialized while producing an inactive Community Release, shadowed, and promoted through the existing Manifest process.

The selected exact Variant is read from the matching immutable Gear Release. Its `itemLevel`, slot, status and variant identity must match the v2 source claim. Any mismatch is a release/import blocker, not a precedence decision.

### 3.2 Pure import projector

`server/community_template_import.py` remains a pure mapper. Its replacement v2 projector receives only the sealed winner selection, scoped exact Variants, scoped generic Item metadata, scoped sources and applicable canonical Options. It must:

1. Require the complete required-slot set and exactly one verified Variant per `(itemId, variantKey, slot)`.
2. Require the source `observedItemLevel` and exact Variant level to be equal and positive.
3. Read name/image only as verified metadata for the same `itemId`; never read generic `itemLevel` as selected gear authority.
4. Reconcile every observed enhancement occurrence to exactly one usable canonical option and validate it against the Resolver constraints.
5. Return `blocked` on the first accumulated proof failure, with stable bounded codes such as `template_import_missing_observed_level`, `template_import_variant_level_mismatch`, `template_import_missing_icon`, `template_import_unmapped_enhancement` and `template_import_constraint_mismatch`.
6. Construct the existing canonical Selection Intent and let the existing Resolver remain final owner of legality, constraints and resolved state.

The projector has no database, HTTP, pointer, sync or frontend side effects. `server/gear_release_store.py` owns the scoped immutable read; `gear_resolver` and `gear_rule_matrix` retain their present fact-owner boundaries.

### 3.3 Import response v2

The additive response revision is `websim-community-template-import-v2`:

```json
{
  "contractRevision": "websim-community-template-import-v2",
  "status": "verified",
  "template": { "id": "observed_profile_mage_frost", "profileHash": "opaque-profile-fingerprint", "gearHash": "opaque-gear-fingerprint" },
  "manifest": { "manifestRevision": "active-manifest-revision", "pointerGeneration": 16 },
  "importedGearBySlot": {
    "head": {
      "slot": "head",
      "itemId": "250060",
      "variantKey": "verified-variant-key",
      "itemLevel": 292,
      "ilevel": 292,
      "displayName": "虚空粉碎者的面纱",
      "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg"
    }
  },
  "selectionIntent": { "schemaRevision": "selection-intent-v1", "slots": {} },
  "resolvedSnapshot": { "constraints": {}, "resolvedSlots": {} }
}
```

`importedGearBySlot` is the sealed display authority for the post-import slot cards. Its item level and image are not enriched from broad `replacementCandidates` on the client. It is structurally one-to-one with `selectionIntent.slots` and `resolvedSnapshot.resolvedSlots`; the server tests this parity before responding.

The response does not return raw unrecognized enhancement values, broad catalog candidates, or an unverified inferred display field.

## 4. Mini-program and saved-template behavior

The community-import commit path consumes only a `verified` v2 response with a current import serial and the expected Manifest/template identity. It directly commits `importedGearBySlot` to the selected slot state and passes its `iconUrl` through the existing game-asset wrapper. It must not call `matchingGearCandidateForItem` to replace imported item level or image.

The Resolver snapshot remains the authority for attributes and selected canonical enhancements. Slot cards read the sealed per-slot display facts. A failed import leaves the existing verified workbench, sheet and saved state unchanged.

New saves made from a community import record an `importOrigin` containing contract revision, template ID, source fingerprint and Manifest binding. On replay:

- a saved community import with `importOrigin` may self-heal only by re-requesting a verified import whose template/source fingerprint and exact selection match the saved origin;
- any changed source fingerprint, missing v2 proof, or blocked revalidation makes that labelled community import explicitly non-applicable and asks the player to re-import;
- legacy saves have no reliable origin marker and are never described as a current community-player source. They may self-heal only when every persisted slot can be revalidated against the current immutable exact `itemId + variantKey`; the revalidated Variant and Item metadata replace the persisted display level and image. A missing Variant, level disagreement, unavailable image, invalid enhancement or Resolver failure blocks the entire saved apply;
- player-authored gear templates keep their existing save/Resolve path. The same exact-variant rehydration protects their display fields, but it does not re-label them as community imports.

This rule deliberately favors honest re-import over silently replaying the known `197` corruption.

## 5. Compatibility, rollout and non-goals

This is a strict release-scoped cutover, not a request-time migration. The release sequence is mandatory:

1. Deploy a compatible reader that recognizes `community-template-import-evidence-v1` but keeps the community import action visibly unavailable when the active Manifest still points to a v1 Community Release.
2. Materialize an inactive v2 Community Release from the observed source, shadow it against the intended Gear Release, and prove every importable winner has complete exact-level and image metadata.
3. Switch the Manifest only to that validated v2 Community Release, then enable the community import action for the matching v2 client/server contract.
4. If the v2 Release is absent, stale, incomplete or rolled back, keep browse available but return the bounded unavailable/blocked import state; never fall back to v1 partial import.

No SQLite fallback, external fetch, release-pointer shortcut, generic catalog expansion or background sync is permitted on the import request path.

The existing single atomic import request and lazy later slot editing remain. This design does not optimize generic slot browse, alter public observed-only eligibility, make recommendations, change SimC calculations, or rewrite old personal templates.

Rollback is code/feature rollback to a temporary unavailable import action, not a return to the older partial-success behavior. Because imports remain read-only, no data restore is required.

## 6. Impact map

| Classification | Surfaces | Required evidence |
| --- | --- | --- |
| `must_change` | observed-template materialization/release projection, `server/gear_release_store.py`, `server/community_template_import.py`, import route, `pages/builds/detail.js`, saved-template metadata and focused tests | exact level/image/enhancement/capacity parity and atomic blocked behavior |
| `must_not_change` | Active Manifest ownership, release-pointer controls, public observed-only eligibility, generic initial/slot browse, Resolver/SimC owner boundaries, sync behavior | contract and public shadow regression coverage |
| `risk_unknown` | whether every current observed winner preserves source item level and verified image metadata; whether v1 saved community templates contain a sufficient source fingerprint | release inventory and negative fixture proof before candidate promotion |
| `evidence_required` | source claim, scoped Variant, Item image metadata, canonical option mapping, constraints, frontend card and saved replay | targeted tests, one final CI/full gate, candidate runtime parity and real WeChat import/replay acceptance |

## 7. Acceptance and release proof

Local tests must cover at least:

1. a selected exact Variant at `292` alongside a generic Item at `197`; response and slot card remain `292`;
2. generic item metadata may provide a verified image but cannot replace selected level or variant;
3. missing observed level, variant-level mismatch, missing image, unavailable Variant, unmapped gem/enchant/embellishment, or capacity contradiction blocks the whole import with no committed changes;
4. all required slots for the frozen observed reference are present; gem order and duplicate occurrences remain exact; enchant and embellishment selections and maxima match Resolver constraints;
5. imported cards render the sealed image and level without candidate fallback;
6. a v2 saved community import revalidates and replays only with matching source identity, while a legacy/corrupted saved import is explicitly blocked;
7. existing normal editor, personal-template, initial/slot browse, Resolve/Profile and public observed-only tests remain unchanged.

Before merge, the final PR head requires one candidate deployment under the existing Harness runtime gate. It records the branch/commit and runtime file parity, PostgreSQL-only runtime and Active Manifest identity, v2 release source coverage, import/Resolve/Profile smoke, 40-spec public observed-only shadow, timer/backflow/log state and rollback path. The real WeChat proof imports the frozen reference, checks every required slot's image and exact item level against the sealed expected vector, confirms gem order/duplicates, enchants, embellishments and capacities, saves it, and verifies replay or the expected explicit block.

No completion claim is valid from unit tests, HTTP 200, aggregate average item level, or a successful systemd job alone.
