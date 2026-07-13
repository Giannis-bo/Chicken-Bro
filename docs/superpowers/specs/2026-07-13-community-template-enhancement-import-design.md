# Community Template Enhancement Import Design

**Date:** 2026-07-13

**Status:** implemented and exact-candidate/live-WeChat verified at `52da68e`; pending merge

**Scope:** equipment simulator community-template import, canonical enhancement facts, and enhancement-sheet slot visibility

## Problem

Importing a public `raiderio_observed_profile` community gear template currently imports the equipment instances but leaves the visible gem, enchant, and embellishment configuration empty. The attribute panel reports `0/0`, and the enhancement sheet says that no selected gear is configurable.

This is not an upstream-data absence. The live `mage/frost` template `observed_profile_mage_frost` includes verified observed `gem_id`, `enchant_id`, and `embellishment` values on its `gearItems`. A live Resolve request for the same template currently returns those raw values inside `resolvedSlots[*].simcOptions`, while simultaneously returning empty `selectedOptions` and all-zero enhancement constraints. The execution input and the visible editor therefore disagree.

## Root Cause

Two boundaries lose different parts of the same fact:

1. `pages/builds/detail.js` imports only explicit template-level `enhancementBySlot`. Public observed templates instead carry their enhancement values on individual `gearItems`. `communityTemplateEnhancementIntentBySlot(...)` therefore produces an empty Intent.
2. `server/pg_gear_authority_loader.py` projects `socketCount`, `canEnchant`, and `canEmbellish` only from explicit fields in the stored item payload. The active immutable Gear Release contains authoritative item metadata and verified variant facts, but does not materialize those derived capability fields. Resolve consequently emits zero/false constraints, and the canonical frontend correctly hides every enhancement slot.

The current behavior is especially misleading because verified variant `simcOptions` still carry raw enhancement values into the resolved SimC item lines. The simulation may consume an enhancement that the UI reports as absent.

## Goals

- Import every community-template gem, enchant, and embellishment that can be reconciled to current verified option authority.
- Preserve multiple gems in their observed order when the exact verified variant proves multiple sockets.
- Make Resolve constraints accurately describe the selected exact gear instances.
- Show every evidence-backed configurable slot in the enhancement sheet.
- Keep unmatched observed enhancement facts visible and explicit instead of silently deleting them or pretending they are editable.
- Keep the backend as the only final legality and SimC serialization authority.

## Non-goals

- Trusting arbitrary client-provided raw SimC IDs.
- Expanding the public template policy beyond active real-player observed templates.
- Adding low-quality gem/enchant options, new embellishment catalog entries, Catalyst, set-bonus overrides, or proc configuration.
- Replacing the active Gear/Community Release model or starting a full catalog refresh.

## Chosen Design

### 1. Canonical capability projection

The PostgreSQL Authority Context loader will derive base enhancement capabilities from the same backend-owned item metadata and slot/type rules used by the WebSim gear read model. It must not rely only on pre-materialized `socketCount/canEnchant/canEmbellish` fields.

For an exact verified variant, observed enhancement fields may strengthen only the capability needed to describe that exact instance:

- a slash-separated verified `gem_id` proves at least that many occupied sockets for the exact variant;
- an observed enchant or embellishment proves that the exact resolved instance carries that fact, but does not by itself make unrelated options applicable;
- item type and slot applicability still come from backend rules and verified option records.

The resulting `constraints.slots` remains backend-owned. The frontend must not re-create capability tables.

### 2. Import-time evidence reconciliation

Community import will collect enhancement clues from both explicit template `enhancementBySlot` and each observed `gearItem`.

For every affected slot it will load the existing slot-detail payload when the initial payload does not contain complete options. Reconciliation rules are:

- split observed `gem_id` values into ordered tokens and match every token to a verified, visible, slot-applicable socket option;
- match `enchant_id` and `embellishment` by exact normalized SimC value;
- accept only options with stable `optionKey` identity and readable verified display evidence;
- require the option to apply to the current selected item type, including off-hand and embellishment rules;
- never synthesize an option identity from a raw value.

Matched facts become canonical option identities:

```json
{
  "finger1": {
    "gemOptionIds": ["gem-a", "gem-b"],
    "enchantOptionId": "ring-enchant-a"
  },
  "back": {
    "embellishmentOptionId": "arcanoweave-lining"
  }
}
```

Legacy single-value `socketOptionId` remains readable for saved-template compatibility, but new community imports use `gemOptionIds` as the canonical representation.

### 3. Unmatched observed facts

An observed raw enhancement can fail reconciliation because the current release lacks a verified option, readable label, applicable-slot proof, or sufficient socket capacity. Such a fact must not be submitted as a trusted client option.

The gear template itself still imports. Matched enhancements apply immediately; unmatched facts are retained as read-only inherited evidence associated with the canonical resolved slot and produce a concise import warning. The enhancement sheet lists that slot and labels the unmatched fact as inherited/non-editable. It must not silently display `0/0`, silently discard the fact, or let the user confirm a forged option.

### 4. Canonical snapshot and editor state

After Resolve succeeds, the visible attribute panel and enhancement sheet are rebuilt from the matching canonical snapshot plus the reconciled option identities. Local template data cannot override a newer or mismatched snapshot.

The editor behavior is:

- matched imported options appear selected;
- multiple imported gems appear selected up to canonical capacity;
- configurable slots appear even before their heavy option list is loaded;
- selecting a slot lazily loads only that slot's details;
- inherited unmatched facts appear read-only with their evidence state;
- changing an option replaces the inherited value only after a successful canonical Resolve;
- closing the sheet still discards unconfirmed draft changes.

### 5. Fail-closed behavior

- If slot-detail loading fails, import the gear and already verified matches, retain unresolved inherited facts, and show a warning.
- If Resolve rejects an option, keep the last verified snapshot read-only and surface the structured problem.
- If observed gem count exceeds canonical capacity, do not truncate silently; mark the slot unresolved until authority proves the capacity.
- If a template has no enhancement facts, preserve the current normal empty import behavior.

## Data Flow

```text
community template gearItems
        |
        v
raw observed enhancement clues
        |
        +--> slot-detail verified option catalog
        |             |
        |             v
        +------ exact reconciliation ------+
                                           |
                          matched option identities
                                           |
                                           v
                                 Selection Intent / Resolve
                                           |
                                           v
                         canonical constraints + resolved slots
                                           |
                       +-------------------+------------------+
                       v                                      v
             attribute counts                     enhancement sheet
```

## Verification Contract

Implementation must be TDD-first and cover:

### Frontend

- a community template with raw gem/enchant/embellishment values imports matching verified option identities;
- slash-separated gems become ordered `gemOptionIds` and are all visible;
- slot-detail is fetched only for affected incomplete slots;
- unmatched raw facts are retained as read-only warnings and are not submitted as option IDs;
- canonical constraints expose equipment rows before option hydration;
- summary counts, slot badges, saved structured snapshots, and sheet selections agree;
- stale Resolve responses cannot overwrite a newer import/edit.

### Backend

- Authority Context derives socket/enchant/embellishment capabilities from authoritative metadata and exact verified variant evidence;
- exact observed gem count can raise only the exact variant socket capacity;
- unrelated or hidden options remain unavailable;
- forged raw enhancement fields still fail closed;
- Resolver constraints and resolved SimC fields do not contradict selected or inherited enhancement facts.

### Regression and live proof

- targeted frontend and backend suites pass;
- Harness frontend/backend/full profiles pass as required by the diff;
- candidate deployment records branch/commit and runtime-file parity;
- live `mage/frost` community import shows non-zero evidence-backed enhancement state;
- the sheet lists the corresponding slots and loads verified options;
- `/api/websim/gear/resolve` returns truthful constraints and no execution/UI split;
- rollback uses the pre-deploy backup and previous candidate commit.

## Delivery Boundary

This correction is a new Harness-scoped runtime slice on a branch based on `origin/main`. It does not modify the completed Phase 0-5 historical artifacts. Deployment, if performed, must be candidate-first with async sync disabled by default. Any release regeneration or database write discovered to be necessary requires an explicit evidence-backed step in the implementation plan rather than an implicit side effect.
