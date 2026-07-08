# WOW UI System Evidence Promotion Audit

Status: `ui_system_evidence_promotion_clean`

Date: 2026-07-07

This audit scans UI system design docs, plan docs and evidence artifacts for accidental promotion claims. It now allows the explicit `target_locked` decision and the explicit `news_list_detail` active permit, while continuing to forbid runtime and final-acceptance claims without real mini-program evidence.

## Command

```sh
node scripts/ui-system-evidence-promotion-audit.js --require-clean --json
```

Current expected exit code: `0`.

## Current Result

- status: `ui_system_evidence_promotion_clean`
- promotionAllowed=false
- scannedFileCount reflects current docs/artifacts at runtime
- target_locked and active_implementation_permit are allowed only in their explicit decision and permit files
- forbidden status claims remain: `runtime_verified`, `final_accepted`
- forbidden true fields: `targetLocked`, `activePermit`, `activeImplementationPermit`, `pageIntegration`, `runtimeVerified`, `finalAccepted`, `goalComplete`, `completionClaimAllowed`, `runtimeVerifiedAllowed`, `finalAcceptedAllowed`, `implementationAllowed`

## What It Scans

- `docs/design/**/*.md`
- `docs/design/**/*.json`
- `docs/plans/**/*.md`
- `docs/plans/**/*.json`
- `artifacts/ui-system-rebuild/**/*.md`
- `artifacts/ui-system-rebuild/**/*.json`

The scan only treats actual `Status: \`...\`` lines and manifest booleans as promotion claims. Sentences such as "not `runtime_verified`" remain legal guard language.

## Meaning

The current evidence set is clean when target lock and active permit claims appear only in the allowlisted files, and when no document claims runtime verification, final acceptance or goal completion. This does not mean the UI rebuild is complete; it only proves the documentation and artifacts are not over-claiming.

## Next Valid Movement

Keep running this audit whenever a new design doc, plan, manifest or evidence artifact is added. If it fails, remove the false promotion claim or add an explicit allowlist only when the required user confirmation and permit evidence exists.

## Non-Promotion Rule

This audit can only prove `ui_system_evidence_promotion_clean`. It cannot prove `runtime_verified`, `final_accepted` or visual acceptance.
