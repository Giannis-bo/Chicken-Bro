const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

const deployScript = fs.readFileSync(
  path.join(__dirname, '..', 'server', 'deploy_lighthouse.sh'),
  'utf8',
);
const publisherScriptPath = path.join(__dirname, '..', 'server', 'publish_release_evidence.sh');

function runBash(source) {
  return spawnSync('bash', ['-lc', source], { encoding: 'utf8' });
}

test('cloud deploy keeps tracked server data and excludes runtime SQLite only', () => {
  assert.match(deployScript, /--exclude 'server\/data\/wow_news\.sqlite3\*'/);
  assert.doesNotMatch(deployScript, /--exclude 'server\/data'\s/);
});

test('cloud deploy does not upload local development payloads', () => {
  for (const artifact of ['node_modules', 'artifacts', 'backups']) {
    assert.match(
      deployScript,
      new RegExp(`--exclude '${artifact}'\\s`),
      `expected ${artifact} to be excluded from the deployment archive`,
    );
  }
});

test('cloud deploy provisions immutable wow evidence hosting without changing artifact exclusion', () => {
  const bashProbe = spawnSync(process.platform === 'win32' ? 'where.exe' : 'which', ['bash'], { stdio: 'ignore' });
  if (bashProbe.status === 0) {
    assert.doesNotThrow(() => execFileSync('bash', ['-n', path.join(__dirname, '..', 'server', 'deploy_lighthouse.sh')]));
  }
  assert.match(deployScript, /sudo mkdir -p \/var\/www\/wow-evidence\/releases/);
  assert.match(deployScript, /sudo chown -R www-data:www-data \/var\/www\/wow-assets \/var\/www\/wow-media \/var\/www\/wow-evidence/);
  assert.match(deployScript, /location \^~ \/wow-evidence\/releases\//);
  assert.match(deployScript, /try_files \$uri =404;/);
  assert.match(deployScript, /Cache-Control "public, max-age=31536000, immutable" always;/);
  assert.match(deployScript, /Access-Control-Allow-Origin "\*" always;/);
  assert.match(deployScript, /X-Content-Type-Options "nosniff" always;/);
  assert.match(deployScript, /--exclude 'artifacts'\s/);
});

test('release evidence publisher exposes the exact bounded allowlist', () => {
  const result = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    printf '%s\n' "\${PUBLISH_EVIDENCE_ALLOWLIST[@]}"
  `);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.stdout.trim().split('\n'), [
    'artifacts/releases/2026-08-17-s2-official-api-fact-snapshot/official-api-capture-v8',
    'artifacts/releases/2026-08-19-s2-official-api-fact-snapshot/official-capture-inventory-v1',
    'artifacts/releases/2026-08-19-s2-limited-db2-field-expansion',
    'artifacts/releases/2026-08-20-s2-official-api-fact-snapshot/official-api-capture-v11',
    'artifacts/releases/2026-08-20-s2-official-api-fact-snapshot/official-capture-inventory-v11',
    'artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/candidate-final-v1.json',
    'artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/seal-report-set-membership-v1.json',
    'artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/live-smoke-v1.json',
    'artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json',
  ]);
});

test('release evidence publisher validates immutable release ids', () => {
  const ok = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    validate_release_id 2026-08-24-s2-evidence
  `);
  assert.equal(ok.status, 0, ok.stderr);
  assert.equal(ok.stdout.trim(), '2026-08-24-s2-evidence');

  for (const value of ['short', 'Latest-release', '../escape', 'release?x=1']) {
    const failure = runBash(`
      set -euo pipefail
      source ${JSON.stringify(publisherScriptPath)}
      validate_release_id ${JSON.stringify(value)}
    `);
    assert.notEqual(failure.status, 0, value);
    assert.match(failure.stderr, /release-id must match/);
  }
});

test('release evidence publisher remote upload script refuses overwrite and validates absolute root', () => {
  const absoluteRoot = path.join(os.tmpdir(), 'wow-evidence-root');
  const remoteScript = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    build_remote_publish_script ${JSON.stringify(absoluteRoot)} 2026-08-24-s2-evidence
  `);
  assert.equal(remoteScript.status, 0, remoteScript.stderr);
  assert.match(remoteScript.stdout, /\[ -e "\$\{release_dir\}" \]/);
  assert.match(remoteScript.stdout, /release-id already exists on remote host/);
  assert.match(remoteScript.stdout, /mv "\$\{staging_dir\}" "\$\{release_dir\}"/);

  const relativeRoot = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    require_absolute_remote_root relative/path
  `);
  assert.notEqual(relativeRoot.status, 0);
  assert.match(relativeRoot.stderr, /remote root must be an absolute path/);
});
