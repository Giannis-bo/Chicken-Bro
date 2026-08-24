# Midnight Season 2 End Game data root

This directory contains compact, reviewable S2 End Game inputs only. Raw
Battle.net/client/SimC captures belong under the dated candidate evidence
directory in `artifacts/releases/`; this directory must not contain secrets or
request-time generated data.

The repository identity is `midnight-season-2` with `scope=end_game`.
Announcement dates are evidence metadata, not Catalog availability gates.
S1 data and the active S1 Manifest remain separate and immutable.

## Equipment library scope

This is the authoritative product scope for the Midnight Season 2 equipment
library. It contains four logical source categories:

1. `raid`: raids, including lair bosses. The product layer groups lairs under
   raid, while the raw provenance layer keeps `raid` and `lair` source types
   distinct.
2. `mythic_plus`: Mythic Keystone dungeon rewards and their progression tracks.
3. `crafted`: profession recipes, qualities, crafted stats, embellishments and
   their progression relationships.
4. `tier_set`: official S2 tier-set membership and class-set relationships,
   treated as an independent equipment-library dimension.

`tier_set` does not replace an item's acquisition source. A set item may carry
both `raid`/`lair` and `tier_set` provenance; a converted set item must retain
its original item identity, stats and effects while gaining the verified set
membership and set-bonus facts.

The library explicitly excludes ordinary dungeon, Delve, Prey, Great Vault and
world-content source categories. Great Vault is a reward projection, not an
additional equipment-library membership source. This scope is a product
boundary, not a claim that every in-scope S2 fact has already been captured or
verified.

## Bounded DB2 field expansion

The limited DB2 authority contract is recorded in
[`db2-field-allowlist-v1.json`](db2-field-allowlist-v1.json). It is permitted
only to close fields that the official Game Data API does not expose, and only
for roots already derived from captured official item, recipe, current
Mythic+ season, or explicitly targeted official Journal map references (or
their explicitly allowlisted foreign keys). The Journal-to-MapDifficulty
scope is frozen in
[`variant-source-map-policy-v1.json`](variant-source-map-policy-v1.json) and
only binds raw variant contexts to M+/raid source legality.

For the Mythic+ Journal pool, the bounded capture also projects exact
`JournalEncounterItem` rows from the official client DB2. A source membership
is included only when the matching `ItemID` plus `JournalEncounterID` row has
`DifficultyMask=-1`; a matching row set whose masks are all nonnegative is
explicitly excluded as ordinary/heroic/non-Mythic+ Journal difficulty. Missing
or malformed rows stay `UNVERIFIED`. The raw `lair`/source key and item
identity remain in the evidence; this table only filters the membership and
does not create a fifth source.

The contract pins the Blizzard retail client build `12.1.0.69299`, uses
`exact` filters only, rejects full-table CSV and unbounded search, and treats
the Wago endpoint as a transport mirror rather than a fact authority. Only
allowlisted fields are projected into evidence; raw DB2 rows are not persisted.
Missing relations remain `UNVERIFIED`, `partial`, or `blocked`. A bounded DB2
probe has no Catalog, Exact, SimC, Candidate, Active Manifest, or production
promotion authority.

The current bounded DB2 closure is recorded in the dated candidate evidence.
It covers only API-missing fields needed for recipe output/quality, item
variant edges, M+ track/cap relations, Journal item scope, tier conversion
preservation and enhancement serialization. Upgrade costs and currencies are
evidence for legal track/rank transitions (for example, the
`ItemExtendedCost`/`CurrencyTypes` chain); they are not product billing, are
not a fifth source, and do not grant an item Catalog membership. Missing
relations remain `UNVERIFIED`, `partial`, or `blocked`.

The current official API source inventory is recorded in
[`official-capture-inventory-v11`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence/artifacts/releases/2026-08-20-s2-official-api-fact-snapshot/official-capture-inventory-v11/inventory.json),
backed by the immutable [v11 raw capture](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence/artifacts/releases/2026-08-20-s2-official-api-fact-snapshot/official-api-capture-v11/capture-manifest.json).
It observes 443 official item identities: 247 from Mythic+, 131 from raid
including lair, and 65 tier-set members. The capture uses official `us/en_US`
namespaces; its static namespace is `12.1.0.68914`, while the bounded DB2 and
fixed SimC runtime are `12.1.0.69299`, so those authority identities remain
explicitly separate.
Published evidence is mirrored under the immutable cloud base above, but the
runtime reads PostgreSQL/API state and never opens an evidence URL. CI/Harness
may still consume repository-local task packets inside a checkout.

The latest sealed Candidate is
[`candidate-v73`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence/artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/candidate-final-v1.json).
Its normalized Gear payload binds 664 items, 36,881 official source rows,
66,685 variants and 74 enhancement options. The Community gate validates
40/40 expected winners, with 4 rejected and 54 standby templates; the Exact
Registry seals 502 referenced exact rows, 624/624 verified template items,
112 enhancement selections, 464 exact instances and 464 validations, with 65
set-membership items across 13 sets and zero partial/blocked validations.
The candidate release packet is sealed by
[`seal-report-set-membership-v1`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence/artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/seal-report-set-membership-v1.json).

The formal Active Manifest is now generation 41. Its immutable pointer and
rollback pair are recorded in
[`live-smoke-v1`](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence/artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/live-smoke-v1.json):
the release API returns verified data, browse returns replacement candidates,
community import resolves all 16 slots, and a mixed 16-slot replacement
resolves with no problem codes. The global `/api/data/health` remains
`partial` under independent owners and must not be represented as a green
global result.

The v69 and matrix-v25 artifacts remain historical evidence for earlier
candidate closure; they do not override the v73 active pointer or its
rollback. The loader correction that accepts the explicit
`sourceMembershipStatus=verified` marker inside immutable source payloads is
deployed with a remote backup recorded in the live smoke artifact.
