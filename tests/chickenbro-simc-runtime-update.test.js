const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const { spawnSync } = require('node:child_process')

const repositoryRoot = path.resolve(__dirname, '..')
const scriptPath = path.join(repositoryRoot, 'server/chickenbro_simc_runtime_update.sh')
const servicePath = path.join(repositoryRoot, 'server/chickenbro-simc-runtime-update.service')

function read(relativePath) {
  return fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8')
}

test('runtime updater is a content-addressed dry-run by default', () => {
  assert.equal(fs.existsSync(scriptPath), true, 'missing Chickenbro SimC updater')

  const result = spawnSync('bash', [scriptPath], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })

  assert.equal(result.status, 0, result.stderr)
  const payload = JSON.parse(result.stdout)
  assert.equal(payload.mode, 'dry-run')
  assert.equal(payload.mutationAuthorized, false)
  assert.equal(payload.runtimeRoot, '/opt/wow-simc')
  assert.equal(payload.currentLink, '/opt/wow-simc/current')
  assert.equal(payload.sourceRepository, 'simulationcraft/simc')
  assert.equal(payload.targetCommit, null)
  assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, /curl|cmake|Downloading|Building/)
})

test('apply fails closed before network without both exact commit identities', () => {
  const missing = spawnSync('bash', [scriptPath, '--apply'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(missing.status, 0)
  assert.match(missing.stderr, /--apply requires --target-commit/i)

  const targetOnly = spawnSync('bash', [
    scriptPath,
    '--apply',
    '--target-commit', 'a'.repeat(40),
  ], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(targetOnly.status, 0)
  assert.match(targetOnly.stderr, /--apply requires --expected-current-commit/i)
  assert.doesNotMatch(`${missing.stdout}${missing.stderr}${targetOnly.stdout}${targetOnly.stderr}`, /codeload\.github\.com/)
})

test('adopt-current seals the exact existing binary without downloading or switching releases', () => {
  const missing = spawnSync('bash', [scriptPath, '--adopt-current'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(missing.status, 0)
  assert.match(missing.stderr, /--adopt-current requires --expected-current-commit/i)

  const commitOnly = spawnSync('bash', [
    scriptPath,
    '--adopt-current',
    '--expected-current-commit', 'a'.repeat(40),
  ], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
  assert.notEqual(commitOnly.status, 0)
  assert.match(commitOnly.stderr, /--adopt-current requires --expected-current-binary-sha/i)
  assert.doesNotMatch(`${missing.stdout}${missing.stderr}${commitOnly.stdout}${commitOnly.stderr}`, /codeload\.github\.com/)

  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.match(source, /EXPECTED_CURRENT_BINARY_SHA/)
  assert.match(source, /actual current binary SHA does not match --expected-current-binary-sha/)
  assert.match(source, /"status": "adopted_current"/)
  assert.match(source, /"servicesRestarted": False/)
  const identityGate = source.indexOf('actual current binary SHA does not match --expected-current-binary-sha')
  const adoption = source.indexOf('adopt_current_release "${EXPECTED_CURRENT_COMMIT}"', identityGate)
  const download = source.indexOf("curl --proto '=https'")
  assert.ok(identityGate >= 0 && adoption > identityGate, 'binary identity must be exact before adoption')
  assert.ok(download > adoption, 'adoption must finish without entering the source download path')
})

test('runtime updater preserves old releases and atomically switches the fixed current pointer', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')

  assert.match(source, /SOURCE_REPOSITORY="simulationcraft\/simc"/)
  assert.match(source, /SOURCE_ARCHIVE_BASE="https:\/\/codeload\.github\.com\/simulationcraft\/simc\/tar\.gz"/)
  assert.match(source, /TARGET_COMMIT/)
  assert.match(source, /EXPECTED_CURRENT_COMMIT/)
  assert.match(source, /CURRENT_COMMIT.*EXPECTED_CURRENT_COMMIT|EXPECTED_CURRENT_COMMIT.*CURRENT_COMMIT/s)
  assert.match(source, /mktemp -d/)
  assert.match(source, /tarfile/)
  assert.match(source, /cmake -S/)
  assert.match(source, /cmake --build/)
  assert.match(source, /spell_query=spell\.name=Bloodlust/)
  assert.doesNotMatch(source, /simc[^\n]*--version|built_simc[^\n]*--version/)
  assert.match(source, /binary\.sha256/)
  assert.match(source, /source-archive\.sha256/)
  assert.match(source, /adopt_current_release/)
  assert.match(source, /legacy-unavailable/)
  assert.match(source, /MAX_SOURCE_ARCHIVE_BYTES/)
  assert.match(source, /MAX_SOURCE_EXPANDED_BYTES/)
  assert.match(source, /--max-filesize "\$\{MAX_SOURCE_ARCHIVE_BYTES\}"/)
  assert.match(source, /BUILD_PARALLELISM="4"/)
  assert.match(source, /flock/)
  assert.match(source, /ln -s/)
  assert.match(source, /mv -Tf/)
  assert.match(source, /mv -T --no-clobber -- "\$\{staged_release\}" "\$\{release_dir\}"/)
  assert.match(source, /target release appeared before atomic publication/)
  assert.match(source, /releases\/\$\{TARGET_COMMIT\}/)

  assert.doesNotMatch(source, /rm\s+-rf|rm\s+-fr/)
  assert.doesNotMatch(source, /github\.com\/repos\/.+branches|SIMC_BRANCH|SIMC_GITHUB_REPO/)
  assert.doesNotMatch(source, /systemctl|service\s+(?:start|restart)|pkill|killall/)
  assert.doesNotMatch(source, /releases[^\n]*(?:rm|delete)|(?:rm|delete)[^\n]*releases/i)

  const capacityGate = source.indexOf('available_bytes=')
  const rollbackAdoption = source.indexOf('adopt_current_release "${CURRENT_COMMIT}"')
  assert.ok(capacityGate >= 0 && rollbackAdoption > capacityGate, 'capacity must fail before rollback metadata mutation')

  const adoptionStart = source.indexOf('adopt_current_release()')
  const adoptionSmoke = source.indexOf('smoke_simc_binary "${current_release}/simc"', adoptionStart)
  const adoptionMetadata = source.indexOf('write_release_metadata_once "${current_release}/.commit"', adoptionStart)
  assert.ok(
    adoptionSmoke > adoptionStart && adoptionMetadata > adoptionSmoke,
    'the current rollback target must pass semantic smoke before adoption metadata is written',
  )

  const lockAcquired = source.indexOf('flock -w 30')
  const alreadyCurrent = source.indexOf('if [[ "${TARGET_COMMIT}" == "${CURRENT_COMMIT}" ]]')
  assert.ok(lockAcquired >= 0 && alreadyCurrent > lockAcquired, 'already-current validation must run under the update lock')
  assert.match(source, /verify_release "\$\{current_release\}" "\$\{CURRENT_COMMIT\}"/)
  assert.match(source, /smoke_simc_binary "\$\{current_release\}\/simc"/)
  assert.match(source, /for command in[^\n]*mktemp/)
})

test('runtime updater cleans its exact work directory before reporting success', () => {
  const source = fs.readFileSync(scriptPath, 'utf8')
  const finalCleanup = source.lastIndexOf('remove_work_directory')
  const successPayload = source.indexOf('python3 - "${EXPECTED_CURRENT_COMMIT}"')

  assert.match(source, /if ! remove_work_directory; then\s+exit_code=1/)
  assert.ok(finalCleanup >= 0 && successPayload > finalCleanup, 'success JSON must follow successful cleanup')
})

test('manual systemd unit needs an ephemeral reviewed trigger and is never enabled automatically', () => {
  assert.equal(fs.existsSync(servicePath), true, 'missing Chickenbro SimC updater unit')
  const service = fs.readFileSync(servicePath, 'utf8')

  assert.match(service, /Description=Chickenbro content-addressed SimulationCraft runtime update/)
  assert.match(service, /User=ubuntu/)
  assert.match(service, /WorkingDirectory=\/opt\/chickenbro/)
  assert.match(service, /EnvironmentFile=\/run\/lock\/chickenbro-simc-runtime-update\.env/)
  assert.match(service, /--apply --target-commit \$\{SIMC_TARGET_COMMIT\} --expected-current-commit \$\{SIMC_EXPECTED_CURRENT_COMMIT\}/)
  assert.match(service, /ExecStartPost=\/usr\/bin\/rm -f -- \/run\/lock\/chickenbro-simc-runtime-update\.env/)
  assert.doesNotMatch(service, /^\[Install\]$/m)
  assert.doesNotMatch(service, /\/opt\/wow-mini-program|\/etc\/wow-backend\.env|wow-mini-program-sync\.lock/)


})

test('legacy retirement protects the replacement updater and names it in the manifest', () => {
  const retire = read('server/retire_chickenbro_legacy_lighthouse.sh')
  const manifest = JSON.parse(read('docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json'))

  const validation = spawnSync('bash', [
    '-c',
    'source "$1"; validate_deletion_target systemd_unit chickenbro-simc-runtime-update.service',
    'test',
    path.join(repositoryRoot, 'server/retire_chickenbro_legacy_lighthouse.sh'),
  ], { cwd: repositoryRoot, encoding: 'utf8' })
  assert.notEqual(validation.status, 0)
  assert.match(validation.stderr, /protected target/i)
  assert.match(retire, /systemd_unit:chickenbro-simc-runtime-update\.service/)
  assert.match(retire, /protected SimulationCraft updater is not loaded/)
  assert.match(retire, /protected SimulationCraft updater changed during retirement/)

  assert.ok(manifest.protectedResources.some((item) => (
    item.kind === 'systemd_unit' && item.target === 'chickenbro-simc-runtime-update.service'
  )))
  for (const target of [
    'wow-simc-runtime-update.service',
    'wow-simc-version-check.service',
    'wow-simc-version-check.timer',
  ]) {
    const resource = manifest.resources.find((item) => item.kind === 'systemd_unit' && item.target === target)
    assert.ok(resource, target)
    assert.equal(resource.replacement, 'chickenbro-simc-runtime-update.service (manual, content-addressed)')
  }
})

test('build discovery accepts a private executable created with umask 077', () => {
  const os = require('node:os')
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'simc-discovery-'))
  try {
    const binary = path.join(dir, 'simc')
    fs.writeFileSync(binary, 'fixture', { mode: 0o700 })
    const statement = fs.readFileSync(scriptPath, 'utf8').split('\n')
      .find((line) => line.trimStart().startsWith('built_simc='))
    const result = spawnSync('bash', ['-c', `${statement}\nprintf '%s' "$built_simc"`], {
      env: { ...process.env, build_dir: dir }, encoding: 'utf8',
    })
    assert.equal(result.status, 0, result.stderr)
    assert.equal(result.stdout, binary)
  } finally {
    fs.rmSync(dir, { recursive: true })
  }
})
