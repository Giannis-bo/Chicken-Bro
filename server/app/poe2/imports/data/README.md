# Finite zhCN mapping v1

This is a deliberately finite, manually authored correspondence set. It does not bundle PoBR data, addohm dictionaries, extracted WeGame responses, image URLs, or account/share identities.

English target facts and the 153 selected passive node IDs are verified against PathOfBuilding-PoE2 commit `7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`. Preserve `UPSTREAM-LICENSE.md` with these derived identifiers. The pinned tree is `src/TreeData/0_5/tree.json`; classes/ascendancies and attribute options are in that file. The three attribute IDs are observed API identifiers and are accepted only with matching display name, exact +5 grant/stat, and a known attribute node.

- Two base correspondences: Akoyan Spear and Amethyst Ring. Fixed `Data/Bases/spear.lua` and `ring.lua` supply English identities; independent research verified source requirements/base characteristics. Equipment properties are separately checked and unsupported fields block conversion.
- Three gems: Explosive Spear, Execute II, Execute III; tier 4 and tier 5 are distinct from the display suffix. Native `gemForBaseName` must resolve the exact dictionary gem ID. Active Explosive Spear additionally requires `ActiveSkills.explosive_spear` in the same snapshot's base_info.
- Five numeric modifier templates: life, fire/cold/lightning/chaos resistance. GGG display disambiguators remain Chinese before exact template matching. Native modLib must parse every translated line. Domain, numeric bound and flags are checked; templates are not arbitrary translation.
- Two quest rewards with exact source choices: Beira and Candlemass. No aggregate-to-choice inference. Empty or nonempty stats only become complete with explicit full choice provenance and explicit resistance penalty.
- No unique, rune, flask/charm, or jewel mapping is asserted. Their sections/gaps remain explicit; nested equipment modifiers still enter the ledger.

The current collector does not attest `source.game_data_version` or `passives.quest_provenance`. Consequently its real snapshots remain needs_input until authoritative provenance is available; the synthetic tests supply both to exercise the bridge. These are mapper inputs only, not new HTTP/user fields or fabricated collector outputs.

Cloud validation checks native import, exact gem IDs, item/gem counts, node allocation/weapon set mode, attribute choice, numeric metrics and export roundtrip. Public preview/issues contain controlled labels, numbers and paths; coverage/ledger contain no source text. `source_hash` is SHA256 of the full sanitized mapper input serialized as sorted compact UTF-8 JSON (distinct from the collector's clock-excluded snapshot_hash).
