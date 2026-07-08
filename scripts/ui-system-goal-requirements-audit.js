#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_OUTPUT_STATUS = 'ui_system_goal_requirements_incomplete'

const REQUIRED_SURFACES = [
  'news_home',
  'news_list_detail',
  'builds_tab',
  'current_spec_workbench',
  'talent_simulator',
  'gear_detail',
  'simc',
  'chickenbro',
  'tasks',
  'profile_templates'
]

const REQUIREMENTS = [
  {
    id: 'goal_reset',
    requirement: 'Active goal and project docs reset the work from pass36/pass37 page repair to UI system rebuild.',
    status: 'complete',
    evidence: [
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md',
      'docs/plans/2026-07-07-wow-ui-system-two-part-goal-sync.md',
      'docs/roadmap.md'
    ],
    missingEvidence: []
  },
  {
    id: 'phase1_inventory',
    requirement: 'Phase 1 inventory covers current pages, components, assets, screenshot evidence and DevTools action state.',
    status: 'source_evidence_complete',
    evidence: [
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md',
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md'
    ],
    missingEvidence: []
  },
  {
    id: 'phase2_problem_register',
    requirement: 'Phase 2 records current systemic problems and prevents returning to page-level pixel patching.',
    status: 'source_evidence_complete',
    evidence: [
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md',
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md',
      'docs/design/2026-07-07-wow-ui-system-diff-scope-audit.md'
    ],
    missingEvidence: []
  },
  {
    id: 'core_page_freeze',
    requirement: 'Core page WXML/WXSS/App shell changes are frozen until target lock and active permit exist.',
    status: 'blocked_gate_active',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-activation-guard.md',
      'docs/design/2026-07-07-wow-ui-system-implementation-gate.md',
      'docs/design/2026-07-07-wow-ui-system-core-page-freeze-preflight.md',
      'scripts/ui-system-core-page-freeze-preflight.js',
      'scripts/ui-system-diff-scope-audit.js'
    ],
    missingEvidence: [
      'passing core page freeze preflight',
      'clean page/app/navigation scope gate',
      'single active implementation permit'
    ]
  },
  {
    id: 'component_owner_system',
    requirement: 'Foundation and surface owner components exist and define geometry ownership before page integration.',
    status: 'component_precheck_evidence',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-foundation-component-contracts.md',
      'docs/design/2026-07-07-wow-ui-system-surface-owner-contracts.md',
      'docs/design/2026-07-07-wow-ui-system-owner-registry-preflight.md',
      'scripts/ui-system-owner-registry-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-browser-component-precheck.md',
      'docs/design/2026-07-07-wow-ui-system-page-adoption-preflight-template.md',
      'scripts/ui-system-page-adoption-preflight.js'
    ],
    missingEvidence: [
      'page adoption under active permits',
      'runtime component crops from real mini-program implementation'
    ]
  },
  {
    id: 'imagegen_asset_boundary',
    requirement: 'Imagegen is limited to low-semantic sliced material; real WoW objects cannot be generated facts.',
    status: 'material_asset_seed_ready',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-asset-manifest-draft.md',
      'docs/design/2026-07-07-wow-ui-system-material-asset-seed.md',
      'scripts/ui-system-material-asset-seed-preflight.js',
      'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json',
      'docs/design/2026-07-07-wow-ui-system-production-asset-manifest-template.md',
      'scripts/ui-system-production-asset-manifest-preflight.js',
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md'
    ],
    missingEvidence: [
      'production asset manifest with exact files, dimensions, owners, package budget and fit strategy'
    ]
  },
  {
    id: 'real_wow_source_boundary',
    requirement: 'Real WoW classes, specs, talents, gear, sources and fact icons come from real interfaces or verified repo/user assets.',
    status: 'source_map_seed_ready',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-asset-manifest-draft.md',
      'docs/design/2026-07-07-wow-ui-system-production-asset-manifest-template.md',
      'scripts/ui-system-production-asset-manifest-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-real-wow-source-map-template.md',
      'scripts/ui-system-real-wow-source-map-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-real-wow-source-map-seed.md',
      'scripts/ui-system-real-wow-source-map-seed-preflight.js',
      'artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json',
      'docs/design/2026-07-07-wow-ui-system-target-lock-proposal.md',
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md'
    ],
    missingEvidence: [
      'locked production source map for every runtime image/object used by integrated pages',
      'valid real WoW source map at artifacts/ui-system-rebuild/runtime/real-wow-source-map.json'
    ]
  },
  {
    id: 'chickenbro_first_class_surface',
    requirement: 'Chickenbro is treated as a first-class surface instead of an old chat shell.',
    status: 'component_precheck_evidence',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck.md',
      'docs/design/2026-07-07-wow-ui-system-chickenbro-component-precheck.md',
      'docs/plans/2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md'
    ],
    missingEvidence: [
      'active Chickenbro permit',
      'runtime screenshots for tab empty, workbench context, generating, complete, failure, topic drawer, focused input and long message scroll'
    ]
  },
  {
    id: 'target_locked_design',
    requirement: 'A user-confirmed target_locked design covers all core surfaces.',
    status: 'missing',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-target-lock-decision-request.md',
      'docs/design/2026-07-07-wow-ui-system-target-lock-decision-brief.md',
      'scripts/ui-system-target-lock-decision-brief-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-target-locked-decision-template.md',
      'scripts/ui-system-target-lock-decision-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-target-lock-readiness-preflight.md',
      'scripts/ui-system-target-lock-readiness-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-first-surface-activation-readiness-preflight.md',
      'scripts/ui-system-first-surface-activation-readiness-preflight.js'
    ],
    missingEvidence: [
      'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md',
      'explicit user target-lock confirmation or written modification'
    ]
  },
  {
    id: 'first_surface_activation_readiness',
    requirement: 'The first bounded surface has machine-checked activation readiness without promoting implementation.',
    status: 'source_evidence_complete',
    evidence: [
      'docs/plans/2026-07-07-wow-ui-system-target-lock-decision-and-news-list-detail-activation-packet.md',
      'artifacts/ui-system-rebuild/20260707-target-lock-decision-and-news-list-detail-activation-packet/manifest.json',
      'docs/design/2026-07-07-wow-ui-system-first-surface-activation-readiness-preflight.md',
      'scripts/ui-system-first-surface-activation-readiness-preflight.js',
      'artifacts/ui-system-rebuild/20260707-first-surface-activation-readiness-preflight/manifest.json'
    ],
    missingEvidence: []
  },
  {
    id: 'active_implementation_permit',
    requirement: 'Exactly one active implementation permit exists before page integration.',
    status: 'missing',
    evidence: [
      'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit-template.md',
      'scripts/ui-system-active-permit-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-first-surface-activation-readiness-preflight.md'
    ],
    missingEvidence: [
      'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md',
      'valid target_locked decision record'
    ]
  },
  {
    id: 'page_integration',
    requirement: 'Core pages compose owner components, bind real data and handle routes under permit.',
    status: 'blocked',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-implementation-gate.md',
      'scripts/ui-system-implementation-gate.js',
      'docs/design/2026-07-07-wow-ui-system-page-adoption-preflight-template.md',
      'scripts/ui-system-page-adoption-preflight.js'
    ],
    missingEvidence: [
      'target lock',
      'active permit',
      'clean diff scope',
      'passing post-integration page adoption preflight'
    ]
  },
  {
    id: 'runtime_screenshots',
    requirement: 'Every core surface has real WeChat mini-program screenshots across required states and viewports.',
    status: 'missing',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-route-smoke-plan.md',
      'docs/design/2026-07-07-wow-ui-system-route-smoke-execution-template.md',
      'scripts/ui-system-route-smoke-execution-preflight.js'
    ],
    missingEvidence: [
      'real mini-program screenshots for news, builds tab, workbench five states, talents, gear, SimC, Chickenbro, tasks and profile/templates',
      'compact, standard and large viewport evidence'
    ]
  },
  {
    id: 'overlay_redzone_scorecard',
    requirement: 'Runtime implementation is compared with target by crop, overlay, red-zone and scorecard evidence.',
    status: 'missing',
    evidence: [
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md',
      'docs/design/2026-07-07-wow-ui-system-route-smoke-execution-template.md',
      'scripts/ui-system-route-smoke-execution-preflight.js',
      'docs/design/2026-07-07-wow-ui-system-visual-acceptance-scorecard-template.md',
      'scripts/ui-system-visual-acceptance-preflight.js'
    ],
    missingEvidence: [
      'target/current/implementation comparison set',
      'component crop set',
      'overlay metrics',
      'red-zone report',
      'valid visual acceptance scorecard for each core surface'
    ]
  },
  {
    id: 'route_smoke_execution',
    requirement: 'Route smoke covers entry, back, tab switching, expand/collapse, workbench handoffs, Chickenbro actions, tasks and template operations.',
    status: 'missing',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-route-smoke-plan.md',
      'docs/design/2026-07-07-wow-ui-system-route-smoke-execution-template.md',
      'scripts/ui-system-route-smoke-execution-preflight.js'
    ],
    missingEvidence: [
      'valid route smoke execution manifest at artifacts/ui-system-rebuild/runtime/route-smoke-execution-manifest.json',
      'post-integration route logs, screenshots, crops, comparisons, overlays, red-zones and scorecard'
    ]
  },
  {
    id: 'devtools_action_ledger',
    requirement: 'Real verification has low-disturbance DevTools action ledger and captureSafe record.',
    status: 'missing',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-activation-guard.md',
      'docs/design/2026-07-07-wow-ui-system-route-smoke-plan.md',
      'docs/design/2026-07-07-wow-ui-system-devtools-action-ledger-template.md',
      'scripts/ui-system-devtools-action-ledger-preflight.js'
    ],
    missingEvidence: [
      'DevTools action ledger for capture-safe runtime run',
      'captureSafe=true record',
      'login-state incident audit if capture fails'
    ]
  },
  {
    id: 'non_promotion_guard',
    requirement: 'No draft, component precheck, browser evidence or blocked gate can be promoted to runtime_verified/final_accepted.',
    status: 'complete',
    evidence: [
      'docs/design/2026-07-07-wow-ui-system-activation-guard.md',
      'docs/design/2026-07-07-wow-ui-system-implementation-gate.md',
      'docs/plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md'
    ],
    missingEvidence: []
  }
]

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return fs.existsSync(resolvePath(filePath))
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(resolvePath(filePath), 'utf8'))
}

function buildReport() {
  const requirementReports = REQUIREMENTS.map((item) => {
    const existingEvidence = item.evidence.filter(exists)
    const absentEvidence = item.evidence.filter((filePath) => !exists(filePath))
    return {
      ...item,
      evidenceExists: absentEvidence.length === 0,
      existingEvidence,
      absentEvidence
    }
  })
  const incompleteRequirements = requirementReports
    .filter((item) => !['complete', 'source_evidence_complete'].includes(item.status))
    .map((item) => item.id)
  const missingRequirements = requirementReports
    .filter((item) => item.status === 'missing')
    .map((item) => item.id)
  const blockedRequirements = requirementReports
    .filter((item) => item.status === 'blocked' || item.status === 'blocked_gate_active')
    .map((item) => item.id)
  const weakEvidenceRequirements = requirementReports
    .filter((item) => (
      item.status === 'component_precheck_evidence' ||
      item.status === 'draft_boundary_complete' ||
      item.status === 'material_asset_seed_ready' ||
      item.status === 'source_map_seed_ready'
    ))
    .map((item) => item.id)

  let implementationGateStatus = 'unknown'
  let implementationAllowed = false
  const gateManifestPath = 'artifacts/ui-system-rebuild/20260707-implementation-gate/manifest.json'
  if (exists(gateManifestPath)) {
    const gateManifest = readJson(gateManifestPath)
    implementationGateStatus = gateManifest.status
    implementationAllowed = Boolean(gateManifest.implementationAllowed)
  }

  return {
    status: DEFAULT_OUTPUT_STATUS,
    goalComplete: false,
    completionClaimAllowed: false,
    runtimeVerifiedAllowed: false,
    finalAcceptedAllowed: false,
    implementationGateStatus,
    implementationAllowed,
    requiredSurfaces: REQUIRED_SURFACES,
    counts: {
      total: requirementReports.length,
      complete: requirementReports.filter((item) => item.status === 'complete').length,
      sourceEvidenceComplete: requirementReports.filter((item) => item.status === 'source_evidence_complete').length,
      weakEvidence: weakEvidenceRequirements.length,
      blocked: blockedRequirements.length,
      missing: missingRequirements.length
    },
    incompleteRequirements,
    missingRequirements,
    blockedRequirements,
    weakEvidenceRequirements,
    requirements: requirementReports,
    nextRequiredEvidence: [
      'explicit target lock or written modification',
      'valid target_locked decision record',
      'exactly one active implementation permit',
      'passing core page freeze preflight before page integration',
      'production asset manifest derived from the material asset seed',
      'runtime real WoW source map derived from the source-map seed',
      'clean page/app/navigation diff scope before implementation',
      'real mini-program screenshots, crops, overlay, red-zone, scorecard, route smoke and DevTools ledger after integration'
    ]
  }
}

function main() {
  const args = new Set(process.argv.slice(2))
  const report = buildReport()

  if (args.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`goalComplete=${report.goalComplete}\n`)
    process.stdout.write(`completionClaimAllowed=${report.completionClaimAllowed}\n`)
    process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    process.stdout.write(`blockedRequirements=${report.blockedRequirements.join(',')}\n`)
  }

  if (args.has('--require-complete') && !report.goalComplete) {
    process.exitCode = 7
  }
}

main()
