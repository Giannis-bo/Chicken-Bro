const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const harnessScript = 'scripts/project-harness.js'

function runHarness(args = [], options = {}) {
  return spawnSync(process.execPath, [harnessScript, ...args], {
    encoding: 'utf8',
    ...options
  })
}

function writeFile(filePath, source) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, source)
}

function writeJson(filePath, value) {
  writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`)
}

function baseRequirement(overrides = {}) {
  return {
    schemaVersion: 1,
    slug: 'validator-fixture',
    classification: 'Strict',
    status: 'implementation_allowed',
    goal: 'Validate the executable Harness contract.',
    userValue: 'Reject invalid packets before implementation proceeds.',
    nonGoals: ['No runtime work'],
    currentTruth: {
      sources: ['docs/project-state.json', 'docs/roadmap.md'],
      activeMilestone: 'project_harness_normalization'
    },
    impactMap: {
      mustChange: ['scripts/project-harness.js'],
      mustNotChange: ['server runtime'],
      evidenceRequired: ['local tests']
    },
    ownership: {
      factOwner: 'docs/project-state.json',
      consumers: ['scripts/project-harness.js']
    },
    engineeringHealth: {
      status: 'health_safe',
      reason: 'Tooling-only fixture.'
    },
    acceptanceEvidence: ['node --test tests/project-harness.test.js'],
    releaseTrigger: 'docs_tooling_only',
    rollback: ['code_rollback'],
    decisionLog: [
      {
        date: '2026-07-10',
        decision: 'Fixture decision.'
      }
    ],
    ...overrides
  }
}

function baseEvidence(overrides = {}) {
  return {
    schemaVersion: 1,
    slug: 'validator-fixture',
    requirementSlug: 'validator-fixture',
    status: 'local_verified',
    highestEvidenceLevel: 'local_verified',
    branch: 'codex/validator-fixture',
    commit: 'pending_pr_head',
    scope: ['harness'],
    verification: [
      {
        command: 'node --test tests/project-harness.test.js',
        status: 'pass'
      }
    ],
    candidateDeployment: {
      status: 'not_applicable',
      reason: 'Docs/tooling-only fixture.'
    },
    runtimeEvidence: [],
    risks: [],
    rollback: ['code_rollback'],
    cleanup: {
      required: false
    },
    archivedReferences: ['docs/project-state.json'],
    summary: 'Valid fixture.',
    ...overrides
  }
}

function writeHarnessFixture(root, requirement = baseRequirement(), evidence = baseEvidence()) {
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
    ''
  ].join('\n'))
  writeFile(path.join(root, 'docs/roadmap.md'), '# Roadmap\n')
  writeFile(path.join(root, 'docs/README.md'), '# Docs\n')
  writeJson(path.join(root, 'docs/project-state.json'), {
    schemaVersion: 1,
    activeReleaseArtifact: 'artifacts/releases/fixture'
  })
  writeJson(path.join(root, 'artifacts/releases/fixture/requirement.json'), requirement)
  writeJson(path.join(root, 'artifacts/releases/fixture/evidence.json'), evidence)
}

function runHarnessCheck(root, extraArgs = []) {
  return runHarness([
    '--root',
    root,
    '--json',
    '--check',
    '--requirement-file',
    'artifacts/releases/fixture/requirement.json',
    '--evidence-file',
    'artifacts/releases/fixture/evidence.json',
    ...extraArgs
  ])
}

function parseJsonOutput(result) {
  assert.equal(result.stderr, '')
  return JSON.parse(result.stdout)
}

test('project harness emits the current repo-native harness manifest as read-only JSON', () => {
  const result = runHarness(['--json', '--slug', 'harness-smoke', '--date', '2026-07-09'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.status, 'project_harness_manifest_ready')
  assert.equal(manifest.schemaVersion, 1)
  assert.equal(manifest.harness.version, 'v0.5')
  assert.equal(manifest.harness.source, 'docs/harness.md')
  assert.equal(manifest.safety.noNetwork, true)
  assert.equal(manifest.safety.repositoryRemoteSyncPreapproved, true)
  assert.equal(manifest.safety.repositoryRemoteSyncScope, 'configured_project_remote_only')
  assert.equal(manifest.safety.autonomousProgressionEnabled, true)
  assert.equal(manifest.safety.noDeploy, true)
  assert.equal(manifest.safety.noSsh, true)
  assert.equal(manifest.safety.productionWrites, false)
  assert.equal(manifest.evidencePacket.status, 'not_attached')
  assert.equal(manifest.write.enabled, false)
  assert.equal(manifest.evidence.dataHealth.status, 'not_collected')
  assert.equal(manifest.evidence.deploySmoke.status, 'not_run')
  assert.equal(manifest.evidence.localTests.status, 'not_run')
  assert.ok(Array.isArray(manifest.riskMatrix))
  assert.deepEqual(Object.keys(manifest.gates).sort(), [
    'autonomousProgression',
    'candidateDeployment',
    'currentTruth',
    'engineeringHealth',
    'evidencePromotion',
    'feedbackLoop',
    'impactMap',
    'ownershipContract',
    'repositoryRemoteSync',
    'releaseRollback',
    'requirementChallenge'
  ].sort())
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/project-state.json' && source.exists))
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/roadmap.md' && source.exists))
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/backend-owner-map.json' && source.exists))
  assert.ok(manifest.gates.engineeringHealth.hotspotFiles.some((file) => file.path === 'server/websim_payload.py' && file.exists))
  assert.equal(manifest.gates.repositoryRemoteSync.preapprovedForConfiguredProjectRemote, true)
  assert.equal(manifest.gates.autonomousProgression.continueWithoutStepByStepApproval, true)
  assert.ok(manifest.gates.autonomousProgression.stopForConfirmationWhen.includes('clear_blocker'))
  assert.equal(manifest.gates.candidateDeployment.requiredBeforeMergeForRuntimeChanges, true)
  assert.ok(manifest.gates.candidateDeployment.runtimeChangeSurfaces.includes('pg_read_model'))
  assert.ok(manifest.gates.candidateDeployment.requiredEvidence.includes('candidate_deploy_or_preview_smoke'))
  assert.ok(manifest.gates.releaseRollback.rollbackStrategies.includes('resync_repair'))
})

test('project harness writes a local release manifest only when --write is requested', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-'))
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
    '',
    '## Policy Change Log',
    '',
    '| Version | Date | Change |',
    '| --- | --- | --- |',
    '| v9.9 | 2099-01-02 | Fixture policy. |',
    ''
  ].join('\n'))
  writeFile(path.join(root, 'docs/roadmap.md'), '# Roadmap\n')
  writeFile(path.join(root, 'docs/README.md'), '# Docs\n')

  const result = runHarness([
    '--root',
    root,
    '--json',
    '--write',
    '--date',
    '2026-07-09',
    '--slug',
    '../Harness Smoke!!'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.harness.version, 'v9.9')
  assert.equal(manifest.write.enabled, true)
  assert.equal(manifest.release.date, '2026-07-09')
  assert.equal(manifest.release.slug, 'harness-smoke')
  assert.equal(
    manifest.write.path,
    'artifacts/releases/2026-07-09-harness-smoke/manifest.json'
  )

  const writtenManifestPath = path.join(root, manifest.write.path)
  assert.ok(fs.existsSync(writtenManifestPath), 'manifest should be written under local artifacts/releases')
  const writtenManifest = JSON.parse(fs.readFileSync(writtenManifestPath, 'utf8'))
  assert.equal(writtenManifest.harness.version, 'v9.9')
  assert.equal(writtenManifest.safety.productionWrites, false)
  assert.equal(writtenManifest.repo.git.status, 'not_git_repository')
})

test('project harness sanitizes release path segments before writing artifacts', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-path-'))
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
    ''
  ].join('\n'))
  writeFile(path.join(root, 'docs/roadmap.md'), '# Roadmap\n')
  writeFile(path.join(root, 'docs/README.md'), '# Docs\n')

  const result = runHarness([
    '--root',
    root,
    '--json',
    '--write',
    '--date',
    '../../../outside',
    '--slug',
    '../Harness Smoke!!'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.release.date, 'outside')
  assert.equal(manifest.release.slug, 'harness-smoke')
  assert.equal(
    manifest.write.path,
    'artifacts/releases/outside-harness-smoke/manifest.json'
  )
  assert.ok(
    path.resolve(root, manifest.write.path).startsWith(path.resolve(root, 'artifacts/releases') + path.sep),
    'write path should remain under artifacts/releases'
  )
  assert.ok(fs.existsSync(path.join(root, manifest.write.path)))
})

test('project harness loads a local evidence packet without executing it', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-evidence-'))
  writeFile(path.join(root, 'docs/harness.md'), [
    '# Repo-native Harness',
    '',
    '> Harness version：v9.9。',
    '> 最后更新：2099-01-02。',
    ''
  ].join('\n'))
  writeFile(path.join(root, 'docs/roadmap.md'), '# Roadmap\n')
  writeFile(path.join(root, 'docs/README.md'), '# Docs\n')
  writeFile(path.join(root, 'artifacts/releases/sample/evidence.json'), JSON.stringify({
    status: 'local_verified',
    highestEvidenceLevel: 'local_verified',
    scope: ['harness'],
    verification: [
      {
        command: 'node --test tests/project-harness.test.js',
        status: 'pass'
      }
    ],
    risks: [],
    rollback: ['code_rollback'],
    summary: 'Harness evidence packet fixture.'
  }, null, 2))

  const result = runHarness([
    '--root',
    root,
    '--json',
    '--evidence-file',
    'artifacts/releases/sample/evidence.json'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.evidencePacket.status, 'ready')
  assert.equal(manifest.evidencePacket.path, 'artifacts/releases/sample/evidence.json')
  assert.equal(manifest.evidencePacket.declaredStatus, 'local_verified')
  assert.equal(manifest.evidencePacket.highestEvidenceLevel, 'local_verified')
  assert.deepEqual(manifest.evidencePacket.missingFields, [])
})

test('project harness refuses evidence packets outside the repository root', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-evidence-boundary-'))
  const result = runHarness([
    '--root',
    root,
    '--json',
    '--evidence-file',
    '../outside.json'
  ])

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /Refusing evidence file outside repository root/)
})

test('project harness check accepts a valid requirement and evidence packet', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-check-valid-'))
  writeHarnessFixture(root)

  const result = runHarnessCheck(root)

  assert.equal(result.status, 0)
  const check = parseJsonOutput(result)
  assert.equal(check.status, 'project_harness_check_passed')
  assert.deepEqual(check.reasonCodes, [])
})

test('project harness check returns stable reason codes for invalid packets', () => {
  const cases = [
    {
      name: 'invalid requirement enum',
      mutateRequirement: (requirement) => {
        requirement.classification = 'Major'
      },
      reasonCode: 'requirement_invalid_enum'
    },
    {
      name: 'missing strict current truth',
      mutateRequirement: (requirement) => {
        delete requirement.currentTruth
      },
      reasonCode: 'requirement_missing_current_truth'
    },
    {
      name: 'missing strict impact map',
      mutateRequirement: (requirement) => {
        delete requirement.impactMap
      },
      reasonCode: 'requirement_missing_impact_map'
    },
    {
      name: 'missing strict ownership',
      mutateRequirement: (requirement) => {
        delete requirement.ownership
      },
      reasonCode: 'requirement_missing_ownership'
    },
    {
      name: 'missing strict acceptance evidence',
      mutateRequirement: (requirement) => {
        requirement.acceptanceEvidence = []
      },
      reasonCode: 'requirement_missing_acceptance_evidence'
    },
    {
      name: 'missing strict rollback',
      mutateRequirement: (requirement) => {
        requirement.rollback = []
      },
      reasonCode: 'requirement_missing_rollback'
    },
    {
      name: 'slug mismatch',
      mutateEvidence: (evidence) => {
        evidence.requirementSlug = 'other-fixture'
      },
      reasonCode: 'packet_slug_mismatch'
    },
    {
      name: 'implementation evidence before implementation allowed',
      mutateRequirement: (requirement) => {
        requirement.status = 'requirement_challenged'
      },
      reasonCode: 'requirement_not_implementation_allowed'
    },
    {
      name: 'evidence level exceeds local proof',
      mutateEvidence: (evidence) => {
        evidence.highestEvidenceLevel = 'live_verified'
      },
      reasonCode: 'evidence_level_exceeds_proof'
    },
    {
      name: 'runtime live evidence lacks candidate deployment proof',
      mutateRequirement: (requirement) => {
        requirement.releaseTrigger = 'backend_api'
      },
      mutateEvidence: (evidence) => {
        evidence.highestEvidenceLevel = 'live_verified'
        evidence.candidateDeployment = { status: 'missing' }
      },
      reasonCode: 'runtime_candidate_deployment_missing'
    },
    {
      name: 'missing archived reference',
      mutateEvidence: (evidence) => {
        evidence.archivedReferences = ['docs/missing-artifact.json']
      },
      reasonCode: 'artifact_reference_missing'
    }
  ]

  for (const testCase of cases) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `wow-project-harness-${testCase.name.replace(/[^a-z0-9]+/gi, '-')}-`))
    const requirement = baseRequirement()
    const evidence = baseEvidence()
    if (testCase.mutateRequirement) testCase.mutateRequirement(requirement)
    if (testCase.mutateEvidence) testCase.mutateEvidence(evidence)
    writeHarnessFixture(root, requirement, evidence)

    const result = runHarnessCheck(root)

    assert.notEqual(result.status, 0, testCase.name)
    const check = parseJsonOutput(result)
    assert.ok(check.reasonCodes.includes(testCase.reasonCode), `${testCase.name} should include ${testCase.reasonCode}`)
  }
})

test('project harness check reports invalid JSON with a stable reason code', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-invalid-json-'))
  writeHarnessFixture(root)
  writeFile(path.join(root, 'artifacts/releases/fixture/requirement.json'), '{ invalid json')

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  const check = parseJsonOutput(result)
  assert.ok(check.reasonCodes.includes('requirement_invalid_json'))
})

test('project harness check refuses requirement packets outside the repository root', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-requirement-boundary-'))

  const result = runHarness([
    '--root',
    root,
    '--json',
    '--check',
    '--requirement-file',
    '../outside.json',
    '--evidence-file',
    'artifacts/releases/fixture/evidence.json'
  ])

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /Refusing requirement file outside repository root/)
})

test('project harness check never executes commands listed in packets', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-command-boundary-'))
  const markerPath = path.join(root, 'command-was-executed')
  writeHarnessFixture(root, baseRequirement(), baseEvidence({
    verification: [
      {
        command: `${process.execPath} -e "require('fs').writeFileSync('${markerPath}', 'bad')"`,
        status: 'pass'
      }
    ]
  }))

  const result = runHarnessCheck(root)

  assert.equal(result.status, 0)
  assert.ok(!fs.existsSync(markerPath), 'validator must not execute verification commands from packets')
})

test('project harness check fails when a critical changed file has no owner map hit', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-owner-gap-'))
  writeHarnessFixture(root)
  writeFile(path.join(root, 'server/websim_payload.py'), 'before = True\n')
  spawnSync('git', ['init'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.email', 'codex@example.com'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.name', 'Codex'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['commit', '-m', 'base'], { cwd: root, encoding: 'utf8' })
  writeFile(path.join(root, 'server/websim_payload.py'), 'after = True\n')

  const result = runHarnessCheck(root, ['--base', 'HEAD'])

  assert.notEqual(result.status, 0)
  const check = parseJsonOutput(result)
  assert.ok(check.reasonCodes.includes('critical_changed_file_unowned'))
})
