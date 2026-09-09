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
    manualAcceptanceContract: {
      required: false,
      requiredItemIds: []
    },
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
    schemaVersion: 2,
    slug: 'validator-fixture',
    requirementSlug: 'validator-fixture',
    status: 'local_verified',
    highestEvidenceLevel: 'local_verified',
    branch: 'codex/validator-fixture',
    commit: 'pending_pr_head',
    identities: {
      runtime: {
        status: 'not_applicable',
        reason: 'Docs/tooling-only fixture.'
      },
      verification: {
        status: 'bound_at_check',
        kind: 'git_ref',
        value: 'HEAD'
      },
      closure: {
        status: 'pending',
        reason: 'No merge or archive closure has occurred.'
      }
    },
    manualAcceptance: {
      required: false,
      status: 'not_applicable',
      reason: 'No user-visible runtime behavior.',
      items: [],
      rollup: {
        total: 0,
        accepted: 0,
        notRunUserWaived: 0,
        pending: 0
      }
    },
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

function baseManifest(overrides = {}) {
  return {
    schemaVersion: 1,
    status: 'project_harness_manifest_ready',
    release: {
      date: '2099-01-02',
      slug: 'validator-fixture'
    },
    harness: {
      version: 'v9.9',
      source: 'docs/harness.md'
    },
    evidencePacket: {
      status: 'ready',
      path: 'artifacts/releases/fixture/evidence.json'
    },
    write: {
      enabled: true,
      path: 'artifacts/releases/fixture/manifest.json'
    },
    ...overrides
  }
}

function writeHarnessFixture(root, requirement = baseRequirement(), evidence = baseEvidence(), manifest = baseManifest()) {
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
  writeJson(path.join(root, 'artifacts/releases/fixture/manifest.json'), manifest)
}

function initializeGitFixture(root) {
  spawnSync('git', ['init'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.email', 'codex@example.com'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.name', 'Codex'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['commit', '-m', 'checked head'], { cwd: root, encoding: 'utf8' })
  return spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim()
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
    '--manifest-file',
    'artifacts/releases/fixture/manifest.json',
    ...extraArgs
  ])
}

function parseJsonOutput(result) {
  assert.equal(result.stderr, '')
  return JSON.parse(result.stdout)
}

test('project harness exposes help without running a manifest', () => {
  const result = runHarness(['--help'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')
  assert.match(result.stdout, /Usage: node scripts\/project-harness\.js/)
  assert.doesNotMatch(result.stdout, /project_harness_manifest_ready/)
})

test('project harness rejects unknown options and missing option values', () => {
  const unknown = runHarness(['--dryrun'])
  assert.notEqual(unknown.status, 0)
  assert.match(unknown.stderr, /Unknown option: --dryrun/)

  const missing = runHarness(['--slug'])
  assert.notEqual(missing.status, 0)
  assert.match(missing.stderr, /Missing value for --slug/)
})

test('project harness emits the current repo-native harness manifest as read-only JSON', () => {
  const result = runHarness(['--json', '--slug', 'harness-smoke', '--date', '2026-07-09'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const manifest = JSON.parse(result.stdout)
  assert.equal(manifest.status, 'project_harness_manifest_ready')
  assert.equal(manifest.schemaVersion, 1)
  assert.equal(manifest.harness.version, 'v0.6.4')
  assert.equal(manifest.harness.source, 'docs/harness.md')
  assert.equal(manifest.harness.policyChangeCount, 0)
  assert.equal(manifest.safety.noNetwork, true)
  assert.equal(manifest.safety.repositoryRemoteSyncPreapproved, false)
  assert.equal(manifest.safety.repositoryRemoteSyncScope, 'requires_current_user_authorization')
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
    'lightFixFastLane',
    'ownershipContract',
    'repositoryRemoteSync',
    'releaseRollback',
    'requirementChallenge',
    'superpowersIntegration',
    'taskScopedEvidenceBinding',
    'userAcceptanceClosure',
    'verificationEfficiency'
  ].sort())
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/project-state.json' && source.exists))
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/project-owner-map.json' && source.exists))
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/roadmap.md' && source.exists))
  assert.ok(manifest.gates.currentTruth.sources.some((source) => source.path === 'docs/backend-owner-map.json' && source.exists))
  assert.ok(manifest.gates.engineeringHealth.hotspotFiles.some((file) => file.path === 'server/app/main.py' && file.exists))
  assert.equal(manifest.gates.repositoryRemoteSync.preapprovedForConfiguredProjectRemote, true)
  assert.equal(manifest.gates.autonomousProgression.continueWithoutStepByStepApproval, true)
  assert.deepEqual(manifest.gates.lightFixFastLane, {
    status: 'ready',
    eligibleWhen: [
      'explicit_and_bounded_user_request',
      'light_risk_classification',
      'no_api_data_ownership_runtime_deployment_or_user_promise_semantic_change'
    ],
    executionTopology: 'agent_selected',
    doNotPromptUserToChoose: ['subagents', 'worktree', 'routine_merge_mechanics'],
    formalDesignOrPlanRequired: false,
    singleClarificationOnlyWhenUserVisibleBehaviorIsAmbiguous: true,
    requiredPreImplementationSummary: ['change', 'risk_boundary', 'targeted_verification']
  })
  assert.deepEqual(manifest.gates.superpowersIntegration, {
    status: 'ready',
    policyLayer: 'harness_controls_classification_evidence_release_and_closure',
    sessionStart: 'inspect_exposed_skills_and_select_only_applicable_methods',
    lightFastLane: {
      defaultMethodSet: 'minimal',
      doNotRequire: ['design_or_plan', 'worktree', 'parallel_agents', 'branch_finish_menu'],
      verification: 'harness_selected_targeted_evidence'
    },
    standardStrict: {
      methods: ['brainstorming', 'writing_plans', 'systematic_debugging', 'test_driven_development', 'review', 'verification'],
      rule: 'select_only_when_the_method_reduces_a_concrete_delivery_risk'
    },
    topology: {
      selectedBy: 'agent_under_harness',
      worktree: 'isolate_when_beneficial_without_automatic_dependency_install',
      parallelAgents: 'only_for_genuinely_independent_tasks'
    },
    closure: 'harness_user_acceptance_closure_without_finish_menu',
    completionEvidence: 'fresh_harness_selected_evidence_before_completion_claim'
  })
  assert.deepEqual(manifest.gates.userAcceptanceClosure, {
    status: 'ready',
    trigger: 'explicit_user_acceptance_after_requested_manual_verification',
    sequence: [
      'final_local_cr',
      'commit_task_branch',
      'sync_main_without_history_rewrite',
      'merge_task_branch',
      'rerun_scoped_verification_on_merge_result',
      'push_main',
      'verify_local_and_origin_main_sha_match',
      'refresh_wechat_preview_on_latest_main_when_frontend_changed',
      'remove_task_worktree_and_local_branch',
      'delete_published_task_branch_if_present'
    ],
    stopFor: [
      'local_or_remote_conflict',
      'failed_verification',
      'scope_expansion',
      'operation_outside_existing_approval'
    ]
  })
  assert.ok(manifest.gates.autonomousProgression.stopForConfirmationWhen.includes('clear_blocker'))
  assert.equal(manifest.gates.candidateDeployment.requiredBeforeMergeForRuntimeChanges, true)
  assert.ok(manifest.gates.candidateDeployment.runtimeChangeSurfaces.includes('pg_read_model'))
  assert.ok(manifest.gates.candidateDeployment.requiredEvidence.includes('candidate_deploy_or_preview_smoke'))
  assert.equal(manifest.gates.candidateDeployment.finalRuntimeHeadOnly, true)
  assert.equal(manifest.gates.candidateDeployment.maximumDeploymentsPerFinalRuntimeHead, 1)
  assert.equal(manifest.gates.candidateDeployment.candidateWindow.policy, 'one_runtime_candidate_window_per_repository')
  assert.equal(manifest.gates.evidencePromotion.mergeReadyDoesNotRequireArchived, true)
  assert.deepEqual(manifest.gates.taskScopedEvidenceBinding, {
    status: 'ready',
    ciReleaseSelection: 'unique_complete_packet_from_pr_diff',
    localReleaseSelection: 'explicit_release_or_default_local_release_artifact',
    manifestBinding: 'task_slug_current_harness_evidence_path_and_self_path',
    identityKinds: ['runtime', 'verification', 'closure'],
    runtimeIdentity: 'matching_immutable_candidate_commit_tree_or_build',
    verificationIdentity: 'clean_exact_git_head',
    manualAcceptanceSet: 'exact_requirement_contract_item_ids',
    manualAcceptanceRollup: ['accepted', 'not_run_user_waived', 'pending'],
    staleGlobalPointerCanSatisfyCi: false,
  })
  assert.equal(manifest.gates.verificationEfficiency.docsOnlyProfile, 'harness')
  assert.equal(manifest.gates.verificationEfficiency.normalRuntimeFullProfile, 'ci_exact_final_head')
  assert.equal(manifest.gates.verificationEfficiency.highRiskRuntimeFullProfile, 'local_once_and_ci_exact_final_head')
  assert.equal(manifest.gates.verificationEfficiency.archiveWhenRuntimeTreeUnchanged, 'harness_only')
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
  writeJson(path.join(root, 'artifacts/releases/sample/evidence.json'), baseEvidence({
    summary: 'Harness evidence packet fixture.'
  }))

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
  assert.deepEqual(manifest.evidencePacket.requiredFields, [
    'schemaVersion',
    'slug',
    'requirementSlug',
    'status',
    'highestEvidenceLevel',
    'branch',
    'commit',
    'identities',
    'manualAcceptance',
    'scope',
    'verification',
    'candidateDeployment',
    'runtimeEvidence',
    'risks',
    'rollback',
    'cleanup',
    'archivedReferences',
    'summary'
  ])
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
  const expected = initializeGitFixture(root)

  const result = runHarnessCheck(root)

  assert.equal(result.status, 0)
  const check = parseJsonOutput(result)
  assert.equal(check.status, 'project_harness_check_passed')
  assert.deepEqual(check.reasonCodes, [])
  assert.equal(check.identities.verification.status, 'bound')
  assert.equal(check.identities.verification.commit, expected)
})

test('project harness rejects a stale manifest from another task packet', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-stale-manifest-'))
  writeHarnessFixture(root, baseRequirement(), baseEvidence(), baseManifest({
    release: {
      date: '2099-01-02',
      slug: 'another-task'
    }
  }))

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  assert.ok(parseJsonOutput(result).reasonCodes.includes('manifest_packet_mismatch'))
})

test('project harness binds the manifest to the checked evidence path', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-manifest-evidence-'))
  writeHarnessFixture(root, baseRequirement(), baseEvidence(), baseManifest({
    evidencePacket: {
      status: 'ready',
      path: 'artifacts/releases/another-task/evidence.json'
    }
  }))

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  assert.ok(parseJsonOutput(result).reasonCodes.includes('manifest_evidence_mismatch'))
})

test('project harness requires separate runtime verification and closure identities', () => {
  const cases = [
    {
      name: 'missing identities',
      mutate: (evidence) => delete evidence.identities,
      reasonCode: 'evidence_missing_identities'
    },
    {
      name: 'bound runtime identity without a value',
      mutate: (evidence) => {
        evidence.identities.runtime = { status: 'bound', kind: 'git_commit', value: '' }
      },
      reasonCode: 'evidence_identity_invalid'
    },
    {
      name: 'closure identity before archival closure',
      mutate: (evidence) => {
        evidence.identities.closure = { status: 'bound', kind: 'merge_commit', value: 'abc123' }
      },
      reasonCode: 'closure_identity_exceeds_evidence'
    },
    {
      name: 'runtime identity differs from candidate deployment',
      mutate: (evidence) => {
        evidence.identities.runtime = { status: 'bound', kind: 'build_identity', value: 'runtime-a' }
        evidence.candidateDeployment = { status: 'candidate_verified', buildIdentity: 'runtime-b' }
      },
      reasonCode: 'runtime_identity_mismatch'
    }
  ]

  for (const testCase of cases) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `wow-project-harness-identity-${testCase.name.replace(/[^a-z0-9]+/gi, '-')}-`))
    const evidence = baseEvidence()
    testCase.mutate(evidence)
    writeHarnessFixture(root, baseRequirement(), evidence)

    const result = runHarnessCheck(root)

    assert.notEqual(result.status, 0, testCase.name)
    const check = parseJsonOutput(result)
    assert.ok(check.reasonCodes.includes(testCase.reasonCode), `${testCase.name} should include ${testCase.reasonCode}`)
  }
})

test('project harness rejects branch-only or mismatched runtime identity binding', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-runtime-identity-'))
  const requirement = baseRequirement({ releaseTrigger: 'backend_api' })
  const evidence = baseEvidence({
    status: 'live_verified',
    highestEvidenceLevel: 'live_verified',
    identities: {
      ...baseEvidence().identities,
      runtime: {
        status: 'bound',
        kind: 'git_commit',
        value: 'immutable-runtime-commit'
      }
    },
    candidateDeployment: {
      status: 'candidate_verified',
      branch: 'codex/mutable-candidate-branch',
      smoke: { status: 'pass' },
      timerBackflow: { status: 'not_applicable' }
    },
    runtimeEvidence: [
      { type: 'smoke', status: 'pass' }
    ]
  })
  writeHarnessFixture(root, requirement, evidence)

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  const check = parseJsonOutput(result)
  assert.ok(check.reasonCodes.includes('runtime_identity_mismatch'))
  assert.ok(check.reasonCodes.includes('runtime_candidate_deployment_missing'))
})

test('project harness resolves the verification identity to the exact checked Git HEAD', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-verification-head-'))
  writeHarnessFixture(root)
  const expected = initializeGitFixture(root)

  const result = runHarnessCheck(root, ['--base', 'HEAD'])

  assert.equal(result.status, 0, result.stdout)
  const check = parseJsonOutput(result)
  assert.equal(check.identities.verification.status, 'bound')
  assert.equal(check.identities.verification.commit, expected)
  assert.equal(check.identities.verification.ref, 'HEAD')
})

test('project harness rejects bound verification when checked bytes differ from HEAD', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-verification-dirty-'))
  writeHarnessFixture(root)
  initializeGitFixture(root)
  writeFile(path.join(root, 'uncommitted-change.txt'), 'dirty\n')

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  const check = parseJsonOutput(result)
  assert.ok(check.reasonCodes.includes('verification_worktree_dirty'))
  assert.equal(check.identities.verification.status, 'dirty')
})

test('project harness rejects manual acceptance rollups that do not match their items', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-manual-rollup-'))
  const evidence = baseEvidence({
    manualAcceptance: {
      required: true,
      status: 'pending',
      items: [
        { id: 'news_home', status: 'accepted', evidence: 'real WeChat acceptance' },
        { id: 'gear_detail', status: 'pending' }
      ],
      rollup: {
        total: 2,
        accepted: 2,
        notRunUserWaived: 0,
        pending: 0
      }
    }
  })
  writeHarnessFixture(root, baseRequirement({
    manualAcceptanceContract: {
      required: true,
      requiredItemIds: ['news_home', 'gear_detail']
    }
  }), evidence)

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  assert.ok(parseJsonOutput(result).reasonCodes.includes('manual_acceptance_rollup_mismatch'))
})

test('project harness accepts a truthful manual acceptance matrix with explicit user waiver', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-manual-waiver-'))
  const evidence = baseEvidence({
    manualAcceptance: {
      required: true,
      status: 'complete_with_user_waiver',
      items: [
        { id: 'news_home', status: 'accepted', evidence: 'real WeChat acceptance' },
        { id: 'gear_detail', status: 'not_run_user_waived', authorization: 'User explicitly authorized merge without this route.' }
      ],
      rollup: {
        total: 2,
        accepted: 1,
        notRunUserWaived: 1,
        pending: 0
      }
    }
  })
  writeHarnessFixture(root, baseRequirement({
    manualAcceptanceContract: {
      required: true,
      requiredItemIds: ['news_home', 'gear_detail']
    }
  }), evidence)
  initializeGitFixture(root)

  const result = runHarnessCheck(root)

  assert.equal(result.status, 0, result.stdout)
  assert.deepEqual(parseJsonOutput(result).reasonCodes, [])
})

test('project harness rejects an unproven manual acceptance or user waiver', () => {
  const cases = [
    {
      name: 'accepted item without evidence',
      item: { id: 'news_home', status: 'accepted' },
      reasonCode: 'manual_acceptance_evidence_missing'
    },
    {
      name: 'waived item without user authorization',
      item: { id: 'gear_detail', status: 'not_run_user_waived' },
      reasonCode: 'manual_acceptance_waiver_unproven'
    }
  ]

  for (const testCase of cases) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), `wow-project-harness-manual-proof-${testCase.name.replace(/[^a-z0-9]+/gi, '-')}-`))
    const status = testCase.item.status === 'accepted' ? 'complete' : 'complete_with_user_waiver'
    const evidence = baseEvidence({
      manualAcceptance: {
        required: true,
        status,
        items: [testCase.item],
        rollup: {
          total: 1,
          accepted: testCase.item.status === 'accepted' ? 1 : 0,
          notRunUserWaived: testCase.item.status === 'not_run_user_waived' ? 1 : 0,
          pending: 0
        }
      }
    })
    writeHarnessFixture(root, baseRequirement({
      manualAcceptanceContract: {
        required: true,
        requiredItemIds: [testCase.item.id]
      }
    }), evidence)

    const result = runHarnessCheck(root)

    assert.notEqual(result.status, 0, testCase.name)
    assert.ok(parseJsonOutput(result).reasonCodes.includes(testCase.reasonCode))
  }
})

test('project harness rejects a manual acceptance matrix that omits required items', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-manual-set-'))
  const requirement = baseRequirement({
    manualAcceptanceContract: {
      required: true,
      requiredItemIds: ['news_home', 'gear_detail']
    }
  })
  const evidence = baseEvidence({
    manualAcceptance: {
      required: true,
      status: 'complete',
      items: [
        { id: 'news_home', status: 'accepted', evidence: 'real WeChat acceptance' }
      ],
      rollup: {
        total: 1,
        accepted: 1,
        notRunUserWaived: 0,
        pending: 0
      }
    }
  })
  writeHarnessFixture(root, requirement, evidence)

  const result = runHarnessCheck(root)

  assert.notEqual(result.status, 0)
  assert.ok(parseJsonOutput(result).reasonCodes.includes('manual_acceptance_set_mismatch'))
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
  initializeGitFixture(root)

  const result = runHarnessCheck(root)

  assert.equal(result.status, 0)
  assert.ok(!fs.existsSync(markerPath), 'validator must not execute verification commands from packets')
})

test('project harness check fails when a critical changed file has no owner map hit', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-owner-gap-'))
  writeHarnessFixture(root)
  writeFile(path.join(root, 'server/app/main.py'), 'before = True\n')
  spawnSync('git', ['init'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.email', 'codex@example.com'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.name', 'Codex'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['commit', '-m', 'base'], { cwd: root, encoding: 'utf8' })
  writeFile(path.join(root, 'server/app/main.py'), 'after = True\n')

  const result = runHarnessCheck(root, ['--base', 'HEAD'])

  assert.notEqual(result.status, 0)
  const check = parseJsonOutput(result)
  assert.ok(check.reasonCodes.includes('critical_changed_file_unowned'))
})

test('project harness check fails when a changed project owner domain has no valid fact owner', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-project-harness-project-owner-gap-'))
  writeHarnessFixture(root)
  writeFile(path.join(root, 'apps/mini-taro/src/app.tsx'), 'before = true\n')
  writeJson(path.join(root, 'docs/project-owner-map.json'), {
    schemaVersion: 1,
    criticalDomains: [
      {
        id: 'dual_client',
        status: 'active',
        factOwner: 'unknown',
        changedPathPatterns: ['apps/mini-taro/**'],
        characterization: ['tests/retained-client-boundary.test.js']
      }
    ]
  })
  writeFile(path.join(root, 'tests/retained-client-boundary.test.js'), 'test fixture\n')
  spawnSync('git', ['init'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.email', 'codex@example.com'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['config', 'user.name', 'Codex'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' })
  spawnSync('git', ['commit', '-m', 'base'], { cwd: root, encoding: 'utf8' })
  writeFile(path.join(root, 'apps/mini-taro/src/app.tsx'), 'after = true\n')

  const result = runHarnessCheck(root, ['--base', 'HEAD'])

  assert.notEqual(result.status, 0)
  const check = parseJsonOutput(result)
  assert.ok(check.reasonCodes.includes('critical_changed_file_unowned'))
})
