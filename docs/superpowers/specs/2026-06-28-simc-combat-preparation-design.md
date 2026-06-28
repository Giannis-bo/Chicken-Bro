# SimC Combat Preparation Design

## Goal

Make template SimC runs explicit about buffs and combat preparation, with class/spec boundaries enforced by the backend. A player should see which buffs are active before submitting a task, and the generated profile must not inherit unrelated raid buffs from SimulationCraft defaults.

## Policy

- Every generated or WebSim-derived profile must set `optimal_raid=0`.
- The backend may then add verified self-class raid buffs only:
  - Mage: `override.arcane_intellect=1`
  - Priest: `override.power_word_fortitude=1`
  - Shaman: `override.skyfury=1`
  - Warrior: `override.battle_shout=1`
  - Druid: `override.mark_of_the_wild=1`
- A profile for one class must never receive another class's self-buff. For example, Shadow Priest does not get Arcane Intellect or Skyfury.
- Spec combat preparation is separate from raid buffs. Enhancement Shaman defaults to its own weapon imbues only after the action names pass production SimC smoke.
- Temporary generic effects, such as weapon oil, sharpening stones, combat potions, and Bloodlust/Heroism, are opt-in switches and default off.

## Evidence Gate

Each backend-owned mapping needs a source note and at least one current SimC binary smoke before it is marked `verified`. Missing or unverified mappings must be reported as partial or blocked instead of silently producing trusted DPS.

The frontend must not send raw SimulationCraft action names or override keys. It may only send structured switches such as `temporaryBuffs.bloodlust=true`; the backend serializes them into profile lines.

## Player Copy

`simcReport` carries a `preparation` block:

- `summary`: short player-facing text for submit/confirmation views.
- `items`: visible rows for enabled or disabled buff groups.
- `evidenceState`: `verified`, `partial`, or `blocked`.
- `blockers` and `warnings`: reasons a preparation line was not applied.

Task confirmation, task detail, and task list read this block from `simcReport` or `simcReportSummary`.

## Initial Scope

This implementation locks the baseline contract and the verified self-class raid buff map. It also exposes the reporting shape for spec preparation and temporary generic buffs, but only emits spec preparation lines after local/production SimC smoke confirms the exact action syntax.
