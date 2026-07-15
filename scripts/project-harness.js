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
  'docs/project-state.json',
  'docs/project-owner-map.json',
  'docs/verification-matrix.md',
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

const REQUIREMENT_CLASSIFICATIONS = ['Light', 'Standard', 'Strict']
const REQUIREMENT_STATUSES = [
  'idea',
  'requirement_challenged',
  'requirement_contract_approved',
  'implementation_allowed',
  'local_verified',
  'runtime_verified',
  'deployable',
  'live_verified',
  'archived'
]
const EVIDENCE_LEVELS = [
  'requirement_challenged',
  'requirement_contract_approved',
  'implementation_allowed',
  'local_verified',
  'runtime_verified',
  'deployable',
  'live_verified',
  'archived'
]
const RELEASE_TRIGGERS = [
  'docs_tooling_only',
  'frontend_user_visible',
  'backend_api',
  'pg_read_model',
  'public_payload',
  'health_admin',
  'scheduled_jobs',
  'deploy_scripts',
  'user_visible_runtime'
]
const RUNTIME_RELEASE_TRIGGERS = new Set([
  'backend_api',
  'pg_read_model',
  'public_payload',
  'health_admin',
  'scheduled_jobs',
  'deploy_scripts',
  'user_visible_runtime'
])
const VERIFICATION_STATUSES = ['pass', 'fail', 'blocked', 'not_run']
const CANDIDATE_DEPLOYMENT_PASS_STATUSES = new Set([
  'candidate_verified',
  'preview_verified',
  'live_verified',
  'verified'
])

function parseArgs(argv) {
  const options = {
    root: process.cwd(),
    json: false,
    write: false,
    date: new Date().toISOString().slice(0, 10),
    slug: 'harness',
    evidenceFile: null,
    requirementFile: null,
    check: false,
    base: null
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--json') {
      options.json = true
    } else if (arg === '--write') {
      options.write = true
    } else if (arg === '--check') {
      options.check = true
    } else if (arg === '--root' && argv[index + 1]) {
      options.root = argv[index + 1]
      index += 1
    } else if (arg === '--date' && argv[index + 1]) {
      options.date = argv[index + 1]
      index += 1
    } else if (arg === '--slug' && argv[index + 1]) {
      options.slug = argv[index + 1]
      index += 1
    } else if (arg === '--requirement-file' && argv[index + 1]) {
      options.requirementFile = argv[index + 1]
      index += 1
    } else if (arg === '--evidence-file' && argv[index + 1]) {
      options.evidenceFile = argv[index + 1]
      index += 1
    } else if (arg === '--base' && argv[index + 1]) {
      options.base = argv[index + 1]
      index += 1
    }
  }

  options.root = path.resolve(options.root)
  options.date = sanitizePathSegment(options.date, new Date().toISOString().slice(0, 10))
  options.slug = sanitizeSlug(options.slug)
  if (options.requirementFile) {
    options.requirementFile = relativePathInsideRoot(options.root, options.requirementFile, 'requirement file')
  }
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

function loadJsonPacket(root, relativePath, packetType) {
  if (!relativePath) {
    return {
      status: 'missing',
      path: null,
      reasonCode: `${packetType}_missing_file`
    }
  }

  const fullPath = pathInsideRoot(root, relativePath, `${packetType} file`)
  if (!fs.existsSync(fullPath)) {
    return {
      status: 'missing',
      path: relativePath,
      reasonCode: `${packetType}_missing_file`
    }
  }

  try {
    const packet = JSON.parse(fs.readFileSync(fullPath, 'utf8'))
    if (!packet || typeof packet !== 'object' || Array.isArray(packet)) {
      return {
        status: 'invalid_packet',
        path: relativePath,
        reasonCode: `${packetType}_invalid_json`,
        error: `${packetType} packet must be a JSON object.`
      }
    }
    return {
      status: 'ready',
      path: relativePath,
      packet
    }
  } catch (error) {
    return {
      status: 'invalid_json',
      path: relativePath,
      reasonCode: `${packetType}_invalid_json`,
      error: error && error.message ? error.message : String(error)
    }
  }
}

function addCheckFailure(failures, reasonCode, detail) {
  failures.push({ reasonCode, detail })
}

function nonEmptyArray(value) {
  return Array.isArray(value) && value.length > 0
}

function hasString(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function requirementNeedsStrictFields(requirement) {
  return requirement.classification === 'Standard' || requirement.classification === 'Strict'
}

function validateRequirementPacket(requirement, failures) {
  if (!Number.isInteger(requirement.schemaVersion)) {
    addCheckFailure(failures, 'requirement_invalid_json', 'Requirement schemaVersion must be an integer.')
  }
  if (!hasString(requirement.slug)) {
    addCheckFailure(failures, 'requirement_invalid_json', 'Requirement slug is required.')
  }
  if (!REQUIREMENT_CLASSIFICATIONS.includes(requirement.classification)) {
    addCheckFailure(failures, 'requirement_invalid_enum', 'Requirement classification is not allowed.')
  }
  if (!REQUIREMENT_STATUSES.includes(requirement.status)) {
    addCheckFailure(failures, 'requirement_invalid_enum', 'Requirement status is not allowed.')
  }
  if (!RELEASE_TRIGGERS.includes(requirement.releaseTrigger)) {
    addCheckFailure(failures, 'requirement_invalid_enum', 'Requirement releaseTrigger is not allowed.')
  }
  if (!hasString(requirement.goal) || !hasString(requirement.userValue)) {
    addCheckFailure(failures, 'requirement_invalid_json', 'Requirement goal and userValue are required.')
  }
  if (!nonEmptyArray(requirement.nonGoals) || !nonEmptyArray(requirement.decisionLog)) {
    addCheckFailure(failures, 'requirement_invalid_json', 'Requirement nonGoals and decisionLog must be non-empty arrays.')
  }
  if (!requirement.engineeringHealth || typeof requirement.engineeringHealth !== 'object' || !hasString(requirement.engineeringHealth.status)) {
    addCheckFailure(failures, 'requirement_invalid_json', 'Requirement engineeringHealth.status is required.')
  }

  if (requirementNeedsStrictFields(requirement)) {
    if (!requirement.currentTruth || typeof requirement.currentTruth !== 'object' || !nonEmptyArray(requirement.currentTruth.sources)) {
      addCheckFailure(failures, 'requirement_missing_current_truth', 'Standard and Strict requirements need currentTruth.sources.')
    }
    if (!requirement.impactMap || typeof requirement.impactMap !== 'object' || !nonEmptyArray(requirement.impactMap.mustChange) || !nonEmptyArray(requirement.impactMap.evidenceRequired)) {
      addCheckFailure(failures, 'requirement_missing_impact_map', 'Standard and Strict requirements need impactMap.mustChange and impactMap.evidenceRequired.')
    }
    if (!requirement.ownership || typeof requirement.ownership !== 'object' || !hasString(requirement.ownership.factOwner)) {
      addCheckFailure(failures, 'requirement_missing_ownership', 'Standard and Strict requirements need ownership.factOwner.')
    }
    if (!nonEmptyArray(requirement.acceptanceEvidence)) {
      addCheckFailure(failures, 'requirement_missing_acceptance_evidence', 'Standard and Strict requirements need acceptanceEvidence.')
    }
    if (!nonEmptyArray(requirement.rollback)) {
      addCheckFailure(failures, 'requirement_missing_rollback', 'Standard and Strict requirements need rollback.')
    }
  }
}

function validateEvidencePacket(requirement, evidence, root, failures) {
  if (!Number.isInteger(evidence.schemaVersion)) {
    addCheckFailure(failures, 'evidence_invalid_json', 'Evidence schemaVersion must be an integer.')
  }
  if (!hasString(evidence.slug) || !hasString(evidence.requirementSlug)) {
    addCheckFailure(failures, 'evidence_invalid_json', 'Evidence slug and requirementSlug are required.')
  }
  if (evidence.slug !== requirement.slug || evidence.requirementSlug !== requirement.slug) {
    addCheckFailure(failures, 'packet_slug_mismatch', 'Requirement and evidence slugs must match.')
  }
  if (!EVIDENCE_LEVELS.includes(evidence.status) || !EVIDENCE_LEVELS.includes(evidence.highestEvidenceLevel)) {
    addCheckFailure(failures, 'evidence_invalid_enum', 'Evidence status or highestEvidenceLevel is not allowed.')
  }
  if (requirement.status !== 'implementation_allowed') {
    addCheckFailure(failures, 'requirement_not_implementation_allowed', 'Evidence cannot promote work before requirement status is implementation_allowed.')
  }
  if (!hasString(evidence.branch) || !hasString(evidence.commit)) {
    addCheckFailure(failures, 'evidence_invalid_json', 'Evidence branch and commit are required.')
  }
  if (!nonEmptyArray(evidence.scope) || !nonEmptyArray(evidence.verification) || !nonEmptyArray(evidence.rollback)) {
    addCheckFailure(failures, 'evidence_invalid_json', 'Evidence scope, verification and rollback must be non-empty arrays.')
  }
  if (!Array.isArray(evidence.risks) || !Array.isArray(evidence.runtimeEvidence) || !Array.isArray(evidence.archivedReferences)) {
    addCheckFailure(failures, 'evidence_invalid_json', 'Evidence risks, runtimeEvidence and archivedReferences must be arrays.')
  }
  if (!evidence.cleanup || typeof evidence.cleanup !== 'object' || typeof evidence.cleanup.required !== 'boolean') {
    addCheckFailure(failures, 'evidence_invalid_json', 'Evidence cleanup.required is required.')
  }
  for (const item of Array.isArray(evidence.verification) ? evidence.verification : []) {
    if (!item || typeof item !== 'object' || !hasString(item.command) || !VERIFICATION_STATUSES.includes(item.status)) {
      addCheckFailure(failures, 'evidence_invalid_json', 'Every verification item needs command and allowed status.')
      break
    }
  }

  validateEvidenceLevel(requirement, evidence, failures)
  validateArtifactReferences(root, evidence.archivedReferences, failures)
}

function validateEvidenceLevel(requirement, evidence, failures) {
  if (evidence.highestEvidenceLevel !== 'live_verified') {
    return
  }

  const candidateDeployment = evidence.candidateDeployment || {}
  const candidatePassed = CANDIDATE_DEPLOYMENT_PASS_STATUSES.has(candidateDeployment.status)
  const runtimeEvidence = Array.isArray(evidence.runtimeEvidence) ? evidence.runtimeEvidence : []
  const hasRuntimeProof = runtimeEvidence.some((item) => item && typeof item === 'object' && item.status === 'pass')

  if (!candidatePassed || !hasRuntimeProof) {
    addCheckFailure(failures, 'evidence_level_exceeds_proof', 'live_verified requires current runtime or live proof.')
  }

  if (RUNTIME_RELEASE_TRIGGERS.has(requirement.releaseTrigger)) {
    const hasCandidateIdentity = hasString(candidateDeployment.branch) || hasString(candidateDeployment.commit) || hasString(candidateDeployment.buildIdentity)
    const hasSmoke = hasNestedPass(candidateDeployment, 'smoke') || runtimeEvidence.some((item) => item && item.type === 'smoke' && item.status === 'pass')
    const hasTimerBackflow = hasNestedPass(candidateDeployment, 'timerBackflow') || runtimeEvidence.some((item) => item && item.type === 'timer_backflow' && (item.status === 'pass' || item.status === 'not_applicable'))
    const hasRollback = nonEmptyArray(evidence.rollback)
    if (!candidatePassed || !hasCandidateIdentity || !hasSmoke || !hasTimerBackflow || !hasRollback) {
      addCheckFailure(failures, 'runtime_candidate_deployment_missing', 'Runtime live evidence requires candidate identity, smoke, timer backflow and rollback proof.')
    }
  }
}

function hasNestedPass(parent, key) {
  const value = parent && parent[key]
  return value && typeof value === 'object' && (value.status === 'pass' || value.status === 'not_applicable')
}

function validateArtifactReferences(root, references, failures) {
  if (!Array.isArray(references)) {
    return
  }
  for (const reference of references) {
    if (!hasString(reference)) {
      addCheckFailure(failures, 'artifact_reference_missing', 'Artifact references must be local repository paths.')
      continue
    }
    try {
      const fullPath = pathInsideRoot(root, reference, 'artifact reference')
      if (!fs.existsSync(fullPath)) {
        addCheckFailure(failures, 'artifact_reference_missing', `Missing artifact reference: ${reference}`)
      }
    } catch (error) {
      addCheckFailure(failures, 'artifact_reference_missing', `Invalid artifact reference: ${reference}`)
    }
  }
}

function changedFilesSinceBase(root, base) {
  if (!base) {
    return []
  }
  const result = spawnSync('git', ['diff', '--name-only', base, '--'], {
    cwd: root,
    encoding: 'utf8'
  })
  if (result.status !== 0) {
    return []
  }
  return result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

function validateCriticalChangedFiles(root, base, failures) {
  const changedFiles = changedFilesSinceBase(root, base)
  if (!changedFiles.length) {
    return
  }
  const criticalFiles = changedFiles.filter((filePath) => DEFAULT_HOTSPOT_FILES.includes(filePath))
  for (const criticalFile of criticalFiles) {
    if (!ownerMapHasFile(root, criticalFile)) {
      addCheckFailure(failures, 'critical_changed_file_unowned', `Critical changed file has no owner map hit: ${criticalFile}`)
    }
  }
  validateProjectOwnerMapChangedFiles(root, changedFiles, failures)
}

function ownerMapHasFile(root, filePath) {
  if (projectOwnerMapHasValidDomainForFile(root, filePath)) {
    return true
  }

  const ownerMapPath = pathInsideRoot(root, 'docs/backend-owner-map.json', 'owner map')
  if (!fs.existsSync(ownerMapPath)) {
    return false
  }
  try {
    const ownerMap = JSON.parse(fs.readFileSync(ownerMapPath, 'utf8'))
    return Array.isArray(ownerMap.hotspotFiles) && ownerMap.hotspotFiles.some((entry) => {
      return entry && entry.path === filePath && Array.isArray(entry.owners) && entry.owners.length > 0
    })
  } catch (error) {
    return false
  }
}

function validateProjectOwnerMapChangedFiles(root, changedFiles, failures) {
  const projectOwnerMap = loadProjectOwnerMap(root)
  if (!projectOwnerMap || !Array.isArray(projectOwnerMap.criticalDomains)) {
    return
  }

  for (const changedFile of changedFiles) {
    const domains = projectOwnerMap.criticalDomains.filter((domain) => domainMatchesChangedFile(domain, changedFile))
    for (const domain of domains) {
      if (!validProjectOwnerDomain(domain)) {
        addCheckFailure(
          failures,
          'critical_changed_file_unowned',
          `Changed file ${changedFile} matched ${domain && domain.id ? domain.id : 'unknown domain'} without a valid fact owner.`
        )
      }
    }
  }
}

function projectOwnerMapHasValidDomainForFile(root, filePath) {
  const projectOwnerMap = loadProjectOwnerMap(root)
  if (!projectOwnerMap || !Array.isArray(projectOwnerMap.criticalDomains)) {
    return false
  }
  return projectOwnerMap.criticalDomains.some((domain) => domainMatchesChangedFile(domain, filePath) && validProjectOwnerDomain(domain))
}

function loadProjectOwnerMap(root) {
  const ownerMapPath = pathInsideRoot(root, 'docs/project-owner-map.json', 'project owner map')
  if (!fs.existsSync(ownerMapPath)) {
    return null
  }
  try {
    return JSON.parse(fs.readFileSync(ownerMapPath, 'utf8'))
  } catch (error) {
    return null
  }
}

function validProjectOwnerDomain(domain) {
  return Boolean(
    domain &&
    domain.status !== 'blocked' &&
    hasString(domain.factOwner) &&
    domain.factOwner !== 'unknown'
  )
}

function domainMatchesChangedFile(domain, filePath) {
  if (!domain || !Array.isArray(domain.changedPathPatterns)) {
    return false
  }
  return domain.changedPathPatterns.some((pattern) => pathPatternMatches(pattern, filePath))
}

function pathPatternMatches(pattern, filePath) {
  if (!hasString(pattern)) {
    return false
  }
  if (pattern === filePath) {
    return true
  }
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*/g, '\u0000')
    .replace(/\*/g, '[^/]*')
    .replace(/\u0000/g, '.*')
  return new RegExp(`^${escaped}$`).test(filePath)
}

function buildCheck(options) {
  const failures = []
  const requirementResult = loadJsonPacket(options.root, options.requirementFile, 'requirement')
  const evidenceResult = loadJsonPacket(options.root, options.evidenceFile, 'evidence')

  if (requirementResult.status !== 'ready') {
    addCheckFailure(failures, requirementResult.reasonCode, requirementResult.error || `Requirement packet is ${requirementResult.status}.`)
  }
  if (evidenceResult.status !== 'ready') {
    addCheckFailure(failures, evidenceResult.reasonCode, evidenceResult.error || `Evidence packet is ${evidenceResult.status}.`)
  }

  if (requirementResult.status === 'ready' && evidenceResult.status === 'ready') {
    validateRequirementPacket(requirementResult.packet, failures)
    validateEvidencePacket(requirementResult.packet, evidenceResult.packet, options.root, failures)
    validateCriticalChangedFiles(options.root, options.base, failures)
  }

  const reasonCodes = [...new Set(failures.map((failure) => failure.reasonCode))]
  return {
    schemaVersion: 1,
    status: failures.length ? 'project_harness_check_failed' : 'project_harness_check_passed',
    reasonCodes,
    failures,
    requirement: {
      path: options.requirementFile,
      slug: requirementResult.packet && requirementResult.packet.slug ? requirementResult.packet.slug : null
    },
    evidence: {
      path: options.evidenceFile,
      slug: evidenceResult.packet && evidenceResult.packet.slug ? evidenceResult.packet.slug : null,
      highestEvidenceLevel: evidenceResult.packet && evidenceResult.packet.highestEvidenceLevel ? evidenceResult.packet.highestEvidenceLevel : null
    },
    base: options.base
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
      finalRuntimeHeadOnly: true,
      maximumDeploymentsPerFinalRuntimeHead: 1,
      candidateWindow: {
        policy: 'one_runtime_candidate_window_per_repository',
        beforeWindow: 'sync_with_main_before_final_ci_and_candidate_smoke',
        duringWindow: 'do_not_merge_overlapping_runtime_prs',
        whenHumanAcceptanceWaits: 'release_window_and_defer_expensive_final_candidate_work'
      },
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
    verificationEfficiency: {
      status: 'ready',
      developmentDefault: 'targeted_tests_for_changed_surface',
      docsOnlyProfile: 'harness',
      normalRuntimeFullProfile: 'ci_exact_final_head',
      highRiskRuntimeFullProfile: 'local_once_and_ci_exact_final_head',
      duplicateProfileRule: 'do_not_run_frontend_backend_and_full_serially',
      archiveWhenRuntimeTreeUnchanged: 'harness_only',
      reviewDefault: 'one_independent_whole_branch_review_at_final_head'
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
      oldEvidenceCannotPromoteCurrentState: true,
      mergeReadyDoesNotRequireArchived: true,
      archivedIsDocumentationClosureNotRuntimeMergeGate: true
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

function printCheckHuman(check) {
  process.stdout.write(`status=${check.status}\n`)
  process.stdout.write(`reasonCodes=${check.reasonCodes.join(',')}\n`)
}

function main() {
  try {
    const options = parseArgs(process.argv.slice(2))

    if (options.check) {
      const check = buildCheck(options)
      if (options.json) {
        process.stdout.write(`${JSON.stringify(check, null, 2)}\n`)
      } else {
        printCheckHuman(check)
      }
      process.exitCode = check.status === 'project_harness_check_passed' ? 0 : 1
      return
    }

    const manifest = buildManifest(options)

    if (options.write) {
      writeManifest(options.root, manifest)
    }

    if (options.json) {
      process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`)
    } else {
      printHuman(manifest)
    }
  } catch (error) {
    process.stderr.write(`${error && error.message ? error.message : String(error)}\n`)
    process.exitCode = 1
  }
}

main()
