#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const DEFAULT_HOTSPOT_FILES = [
  'server/websim_payload.py',
  'server/news_backend.py',
  'server/postgres_cache_store.py'
]

const CURRENT_TRUTH_SOURCES = [
  'docs/roadmap.md',
  'docs/README.md',
  'docs/harness.md',
  'docs/backend-owner-map.json'
]

const ROLLBACK_STRATEGIES = [
  'code_rollback',
  'data_restore',
  'feature_hide',
  'config_disable',
  'resync_repair'
]

const EVIDENCE_PACKET_REQUIRED_FIELDS = [
  'status',
  'highestEvidenceLevel',
  'scope',
  'verification',
  'risks',
  'rollback'
]

function parseArgs(argv) {
  const options = {
    root: process.cwd(),
    json: false,
    write: false,
    date: new Date().toISOString().slice(0, 10),
    slug: 'harness',
    evidenceFile: null
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--json') {
      options.json = true
    } else if (arg === '--write') {
      options.write = true
    } else if (arg === '--root' && argv[index + 1]) {
      options.root = argv[index + 1]
      index += 1
    } else if (arg === '--date' && argv[index + 1]) {
      options.date = argv[index + 1]
      index += 1
    } else if (arg === '--slug' && argv[index + 1]) {
      options.slug = argv[index + 1]
      index += 1
    } else if (arg === '--evidence-file' && argv[index + 1]) {
      options.evidenceFile = argv[index + 1]
      index += 1
    }
  }

  options.root = path.resolve(options.root)
  options.date = sanitizePathSegment(options.date, new Date().toISOString().slice(0, 10))
  options.slug = sanitizeSlug(options.slug)
  if (options.evidenceFile) {
    options.evidenceFile = relativePathInsideRoot(options.root, options.evidenceFile, 'evidence file')
  }
  return options
}

function sanitizeSlug(value) {
  return sanitizePathSegment(value, 'harness')
}

function sanitizePathSegment(value, fallback) {
  const slug = String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || fallback
}

function readText(root, relativePath) {
  const fullPath = pathInsideRoot(root, relativePath, 'read path')
  if (!fs.existsSync(fullPath)) {
    return null
  }
  return fs.readFileSync(fullPath, 'utf8')
}

function pathInsideRoot(root, relativePath, label) {
  const rootPath = path.resolve(root)
  const fullPath = path.resolve(rootPath, relativePath)
  if (fullPath !== rootPath && !fullPath.startsWith(`${rootPath}${path.sep}`)) {
    throw new Error(`Refusing ${label} outside repository root: ${relativePath}`)
  }
  return fullPath
}

function relativePathInsideRoot(root, relativePath, label) {
  const fullPath = pathInsideRoot(root, relativePath, label)
  return path.relative(path.resolve(root), fullPath).split(path.sep).join('/')
}

function extractHarnessMetadata(source) {
  if (!source) {
    return {
      version: 'unknown',
      lastUpdated: 'unknown',
      policyChangeCount: 0
    }
  }

  const versionMatch = source.match(/Harness version[：:]\s*([^。\n]+)/)
  const dateMatch = source.match(/最后更新[：:]\s*([^。\n]+)/)
  const policyChangeCount = source
    .split(/\r?\n/)
    .filter((line) => /^\|\s*v\d+\.\d+\s*\|/.test(line))
    .length

  return {
    version: versionMatch ? versionMatch[1].trim() : 'unknown',
    lastUpdated: dateMatch ? dateMatch[1].trim() : 'unknown',
    policyChangeCount
  }
}

function sourceStatus(root, relativePath) {
  const fullPath = pathInsideRoot(root, relativePath, 'source path')
  const exists = fs.existsSync(fullPath)
  return {
    path: relativePath,
    exists,
    sizeBytes: exists ? fs.statSync(fullPath).size : 0
  }
}

function loadEvidencePacket(root, relativePath) {
  if (!relativePath) {
    return {
      status: 'not_attached',
      requiredFields: EVIDENCE_PACKET_REQUIRED_FIELDS,
      note: 'Attach a local evidence packet with --evidence-file when promoting a Standard or Strict requirement.'
    }
  }

  const fullPath = pathInsideRoot(root, relativePath, 'evidence file')
  if (!fs.existsSync(fullPath)) {
    return {
      status: 'missing',
      path: relativePath,
      requiredFields: EVIDENCE_PACKET_REQUIRED_FIELDS
    }
  }

  let packet
  try {
    packet = JSON.parse(fs.readFileSync(fullPath, 'utf8'))
  } catch (error) {
    return {
      status: 'invalid_json',
      path: relativePath,
      error: error && error.message ? error.message : String(error),
      requiredFields: EVIDENCE_PACKET_REQUIRED_FIELDS
    }
  }

  if (!packet || typeof packet !== 'object' || Array.isArray(packet)) {
    return {
      status: 'invalid_packet',
      path: relativePath,
      error: 'Evidence packet must be a JSON object.',
      requiredFields: EVIDENCE_PACKET_REQUIRED_FIELDS
    }
  }

  const fieldsPresent = EVIDENCE_PACKET_REQUIRED_FIELDS.filter((field) => Object.prototype.hasOwnProperty.call(packet, field))
  const missingFields = EVIDENCE_PACKET_REQUIRED_FIELDS.filter((field) => !fieldsPresent.includes(field))

  return {
    status: missingFields.length ? 'incomplete' : 'ready',
    path: relativePath,
    sizeBytes: fs.statSync(fullPath).size,
    requiredFields: EVIDENCE_PACKET_REQUIRED_FIELDS,
    fieldsPresent,
    missingFields,
    declaredStatus: typeof packet.status === 'string' ? packet.status : 'unknown',
    highestEvidenceLevel: typeof packet.highestEvidenceLevel === 'string' ? packet.highestEvidenceLevel : 'unknown',
    summary: typeof packet.summary === 'string' ? packet.summary : ''
  }
}

function lineCount(root, relativePath) {
  const source = readText(root, relativePath)
  if (source === null) {
    return null
  }
  if (source.length === 0) {
    return 0
  }
  return source.split(/\r?\n/).length
}

function buildEngineeringHealthGate(root) {
  const hotspotFiles = DEFAULT_HOTSPOT_FILES.map((filePath) => {
    const count = lineCount(root, filePath)
    return {
      path: filePath,
      exists: count !== null,
      lineCount: count,
      hotspot: count === null ? false : count >= 2000
    }
  })

  return {
    status: 'health_watch',
    requiredForHotspots: true,
    hotspotFiles,
    requiredQuestions: [
      'structure_boundary',
      'behavior_boundary',
      'test_safety_net',
      'performance',
      'availability',
      'data_safety',
      'observability',
      'rollback'
    ]
  }
}

function gitStatus(root) {
  const result = spawnSync('git', ['status', '--short'], {
    cwd: root,
    encoding: 'utf8'
  })

  if (result.status !== 0) {
    return {
      status: 'not_git_repository',
      changedFileCount: 0,
      changedFiles: []
    }
  }

  const changedFiles = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean)

  return {
    status: changedFiles.length ? 'dirty' : 'clean',
    changedFileCount: changedFiles.length,
    changedFiles
  }
}

function buildManifest(options) {
  const harnessSource = readText(options.root, 'docs/harness.md')
  const harness = extractHarnessMetadata(harnessSource)
  const releaseDirectory = `artifacts/releases/${options.date}-${options.slug}`
  const outputPath = `${releaseDirectory}/manifest.json`
  const gates = {
    requirementChallenge: {
      status: 'template_required',
      requiredOutputs: [
        'requirement_contract',
        'opposition_challenge',
        'approach_comparison',
        'acceptance_evidence',
        'risks_degradation_rollback'
      ]
    },
    currentTruth: {
      status: 'ready',
      sources: CURRENT_TRUTH_SOURCES.map((source) => sourceStatus(options.root, source)),
      historicalDocsDefaultToEvidenceOnly: true
    },
    impactMap: {
      status: 'template_required',
      categories: ['must_change', 'must_not_change', 'risk_unknown', 'evidence_required']
    },
    ownershipContract: {
      status: 'template_required',
      ownerPrinciples: [
        'backend_read_model_owns_structured_facts',
        'frontend_consumes_read_model',
        'health_admin_displays_authoritative_state',
        'scheduled_jobs_write_owned_state_only',
        'deploy_scripts_do_not_create_product_judgment'
      ]
    },
    engineeringHealth: buildEngineeringHealthGate(options.root),
    releaseRollback: {
      status: 'template_required',
      rollbackStrategies: ROLLBACK_STRATEGIES,
      liveVerifiedRequiresCurrentOnlineEvidence: true,
      timerBackflowCheckRequired: true
    },
    candidateDeployment: {
      status: 'required_for_runtime_changes',
      requiredBeforeMergeForRuntimeChanges: true,
      runtimeChangeSurfaces: [
        'backend_api',
        'pg_read_model',
        'public_payload',
        'health_admin',
        'scheduled_jobs',
        'deploy_scripts',
        'user_visible_runtime'
      ],
      requiredEvidence: [
        'candidate_deploy_or_preview_smoke',
        'runtime_file_parity_or_build_identity',
        'post_deploy_health_or_endpoint_smoke',
        'timer_backflow_check',
        'rollback_plan'
      ],
      fallbackWhenPreMergeCandidateIsImpossible: 'record_exception_and_post_merge_live_smoke',
      mergeRule: 'merge_after_candidate_smoke_for_runtime_changes'
    },
    repositoryRemoteSync: {
      status: 'ready',
      preapprovedForConfiguredProjectRemote: true,
      allowedOperations: [
        'git_fetch',
        'git_pull_ff_only',
        'git_push',
        'publish_project_branch',
        'create_update_read_merge_project_pr',
        'read_project_commit_status'
      ],
      stillRequiresConfirmation: [
        'force_push',
        'public_history_rewrite',
        'remote_change',
        'git_clone_other_repo',
        'submodule_update',
        'dependency_install',
        'third_party_download',
        'production_operation_without_current_scope'
      ],
      preSyncCheck: 'git status --short --branch'
    },
    autonomousProgression: {
      status: 'ready',
      continueWithoutStepByStepApproval: true,
      defaultContinueWhen: [
        'plan_or_scope_approved',
        'user_says_continue',
        'direct_execution_authorized',
        'next_step_is_in_scope',
        'verification_passes'
      ],
      stopForConfirmationWhen: [
        'clear_blocker',
        'failed_verification_with_tradeoff',
        'product_or_technical_decision_required',
        'scope_expansion',
        'destructive_or_irreversible_operation',
        'local_or_remote_conflict',
        'outside_existing_approval_boundary'
      ],
      interimUpdatePolicy: 'key_state_changes_risks_and_verification_only'
    },
    evidencePromotion: {
      status: 'template_required',
      levels: [
        'requirement_challenged',
        'requirement_contract_approved',
        'implementation_allowed',
        'local_verified',
        'runtime_verified',
        'deployable',
        'live_verified',
        'archived'
      ],
      oldEvidenceCannotPromoteCurrentState: true
    },
    feedbackLoop: {
      status: 'ready',
      findingRequiredForUnexpectedRework: true,
      promotionStatuses: ['finding_only', 'rule_candidate', 'rule_promoted', 'script_candidate']
    }
  }
  const repoGit = gitStatus(options.root)
  const evidencePacket = loadEvidencePacket(options.root, options.evidenceFile)
  const evidence = {
    localTests: {
      status: 'not_run',
      note: 'project-harness.js does not execute tests; attach command output in the release artifact.'
    },
    uiRuntimeEvidence: {
      status: 'not_collected',
      note: 'Attach real mini-program screenshots or DevTools ledger when applicable.'
    },
    dataHealth: {
      status: 'not_collected',
      note: 'Attach current /api/data/health or PG read-model evidence when applicable.'
    },
    deploySmoke: {
      status: 'not_run',
      note: 'Attach live HTTP/API/PG/timer smoke output when deployment is in scope.'
    }
  }

  return {
    schemaVersion: 1,
    status: 'project_harness_manifest_ready',
    generatedAt: new Date().toISOString(),
    release: {
      date: options.date,
      slug: options.slug
    },
    harness: {
      version: harness.version,
      lastUpdated: harness.lastUpdated,
      source: 'docs/harness.md',
      policyChangeCount: harness.policyChangeCount
    },
    safety: {
      noNetwork: true,
      repositoryRemoteSyncPreapproved: true,
      repositoryRemoteSyncScope: 'configured_project_remote_only',
      autonomousProgressionEnabled: true,
      noDeploy: true,
      noSsh: true,
      productionWrites: false
    },
    gates,
    evidencePacket,
    evidence,
    riskMatrix: buildRiskMatrix(gates, repoGit, evidence, evidencePacket),
    repo: {
      git: repoGit
    },
    write: {
      enabled: options.write,
      path: outputPath
    }
  }
}

function buildRiskMatrix(gates, repoGit, evidence, evidencePacket) {
  const risks = []
  const missingCurrentTruth = gates.currentTruth.sources
    .filter((source) => !source.exists)
    .map((source) => source.path)
  if (missingCurrentTruth.length) {
    risks.push({
      id: 'current_truth_missing',
      severity: 'high',
      status: 'blocked',
      detail: `Missing current-truth sources: ${missingCurrentTruth.join(', ')}`
    })
  }
  if (repoGit.status === 'dirty') {
    risks.push({
      id: 'dirty_worktree',
      severity: 'medium',
      status: 'watch',
      detail: `${repoGit.changedFileCount} changed files currently visible to git status.`
    })
  }
  const hotspots = gates.engineeringHealth.hotspotFiles.filter((file) => file.hotspot)
  if (hotspots.length) {
    risks.push({
      id: 'hotspot_files_present',
      severity: 'medium',
      status: 'watch',
      detail: hotspots.map((file) => `${file.path}:${file.lineCount}`).join(', ')
    })
  }
  for (const [id, item] of Object.entries(evidence)) {
    if (item.status === 'not_run' || item.status === 'not_collected') {
      risks.push({
        id: `${id}_missing`,
        severity: 'low',
        status: 'info',
        detail: item.note
      })
    }
  }
  if (evidencePacket.status === 'missing' || evidencePacket.status === 'invalid_json' || evidencePacket.status === 'invalid_packet') {
    risks.push({
      id: 'evidence_packet_unusable',
      severity: 'medium',
      status: 'blocked',
      detail: `Evidence packet is ${evidencePacket.status}.`
    })
  } else if (evidencePacket.status === 'incomplete') {
    risks.push({
      id: 'evidence_packet_incomplete',
      severity: 'low',
      status: 'info',
      detail: `Missing evidence packet fields: ${evidencePacket.missingFields.join(', ')}`
    })
  }
  return risks
}

function writeManifest(root, manifest) {
  const outputPath = releaseArtifactPath(root, manifest.write.path)
  fs.mkdirSync(path.dirname(outputPath), { recursive: true })
  fs.writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`)
}

function releaseArtifactPath(root, relativePath) {
  const releasesRoot = path.resolve(root, 'artifacts/releases')
  const outputPath = path.resolve(root, relativePath)
  if (!outputPath.startsWith(`${releasesRoot}${path.sep}`)) {
    throw new Error(`Refusing to write outside artifacts/releases: ${relativePath}`)
  }
  return outputPath
}

function printHuman(manifest) {
  process.stdout.write(`status=${manifest.status}\n`)
  process.stdout.write(`harnessVersion=${manifest.harness.version}\n`)
  process.stdout.write(`release=${manifest.release.date}-${manifest.release.slug}\n`)
  process.stdout.write(`gitStatus=${manifest.repo.git.status}\n`)
  if (manifest.write.enabled) {
    process.stdout.write(`manifest=${manifest.write.path}\n`)
  }
}

function main() {
  const options = parseArgs(process.argv.slice(2))
  const manifest = buildManifest(options)

  if (options.write) {
    writeManifest(options.root, manifest)
  }

  if (options.json) {
    process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`)
  } else {
    printHuman(manifest)
  }
}

main()
