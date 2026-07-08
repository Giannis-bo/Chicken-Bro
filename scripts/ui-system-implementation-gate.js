#!/usr/bin/env node

const { spawnSync } = require('node:child_process')

const CHECKS = [
  {
    id: 'activation',
    command: ['scripts/ui-system-activation-preflight.js', '--require-activation', '--json'],
    passField: 'activationAllowed',
    expectedBlockedExitCode: 2
  },
  {
    id: 'target_lock_decision',
    command: ['scripts/ui-system-target-lock-decision-preflight.js', '--require-decision', '--json'],
    passField: 'validDecisionRecord',
    expectedBlockedExitCode: 4
  },
  {
    id: 'first_surface_readiness',
    command: ['scripts/ui-system-first-surface-activation-readiness-preflight.js', '--require-ready', '--json'],
    passField: 'readyForTargetLockActivation',
    expectedBlockedExitCode: 18
  },
  {
    id: 'course_correction',
    command: ['scripts/ui-system-refactor-course-correction-preflight.js', '--require-ready', '--json'],
    passField: 'courseCorrectionReady',
    expectedBlockedExitCode: 19
  },
  {
    id: 'active_permit',
    command: ['scripts/ui-system-active-permit-preflight.js', '--surface', 'news_list_detail', '--require-active-permit', '--json'],
    passField: 'implementationAllowed',
    expectedBlockedExitCode: 5
  },
  {
    id: 'diff_scope',
    command: ['scripts/ui-system-diff-scope-audit.js', '--require-no-page-integration', '--summary-json'],
    passField: 'pageScopeBlocked',
    invertPassField: true,
    expectedBlockedExitCode: 3
  }
]

function runCheck(check) {
  const result = spawnSync(process.execPath, check.command, { encoding: 'utf8' })
  let report
  try {
    report = JSON.parse(result.stdout)
  } catch (error) {
    report = {
      parseError: error.message,
      rawStdout: result.stdout
    }
  }
  const rawValue = Boolean(report[check.passField])
  const passed = check.invertPassField ? !rawValue : rawValue
  return {
    id: check.id,
    command: `node ${check.command.join(' ')}`,
    exitCode: result.status,
    expectedBlockedExitCode: check.expectedBlockedExitCode,
    passed,
    status: report.status || 'unknown',
    report,
    stderr: result.stderr
  }
}

function buildGate() {
  const checks = CHECKS.map(runCheck)
  const blockingChecks = checks.filter((check) => !check.passed).map((check) => check.id)
  const implementationAllowed = blockingChecks.length === 0
  const blockingReasons = Array.from(new Set(checks.flatMap((check) => {
    const report = check.report || {}
    return [
      ...(report.blockingReasons || []),
      ...(report.activationBlockingReasons || []),
      ...(report.missingRequirements || [])
    ]
  })))

  return {
    status: implementationAllowed
      ? 'ui_system_implementation_gate_passed'
      : 'ui_system_implementation_gate_blocked',
    implementationAllowed,
    blockingChecks,
    blockingReasons,
    checkedSurface: 'news_list_detail',
    checks,
    nextRequiredEvidence: implementationAllowed
      ? 'page implementation under active permit'
      : 'explicit target lock, valid decision record, course correction, active permit, clean page scope gate'
  }
}

function main() {
  const args = new Set(process.argv.slice(2))
  const report = buildGate()

  if (args.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`implementationAllowed=${report.implementationAllowed}\n`)
    if (report.blockingChecks.length) {
      process.stdout.write(`blockingChecks=${report.blockingChecks.join(',')}\n`)
    }
  }

  if (args.has('--require-implementation') && !report.implementationAllowed) {
    process.exitCode = 6
  }
}

main()
