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

function bashLiteral(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
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
    'artifacts/releases/2026-08-20-s2-journal-item-db2-v1',
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
  assert.match(remoteScript.stdout, /sudo mkdir -p "\$\{remote_root\}"/);
  assert.match(remoteScript.stdout, /sudo mkdir "\$\{staging_dir\}"/);
  assert.match(remoteScript.stdout, /sudo tar -xf - -C "\$\{staging_dir\}"/);
  assert.match(remoteScript.stdout, /sudo mv -Tn "\$\{staging_dir\}" "\$\{release_dir\}"/);
  assert.match(remoteScript.stdout, /if \[ -e "\$\{staging_dir\}" \]; then/);
  assert.match(remoteScript.stdout, /release-id already exists on remote host or lost create-only race/);
  assert.match(remoteScript.stdout, /sudo chown -R www-data:www-data "\$\{release_dir\}"/);
  assert.match(remoteScript.stdout, /sudo rm -rf "\$\{staging_dir\}"/);

  const relativeRoot = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    require_absolute_remote_root relative/path
  `);
  assert.notEqual(relativeRoot.status, 0);
  assert.match(relativeRoot.stderr, /remote root must be an absolute path/);

  const traversalRoot = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    require_absolute_remote_root /var/www/../escape
  `);
  assert.notEqual(traversalRoot.status, 0);
  assert.match(traversalRoot.stderr, /remote root must not contain path traversal/);
});

test('release evidence publisher reports a missing allowlist path', () => {
  const result = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    temp_dir=$(mktemp -d)
    stage_selected_paths "$temp_dir" does/not/exist
  `);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /allowlist path is missing: does\/not\/exist/);
});

test('release evidence publisher rejects symlinked allowlist content', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-evidence-symlink-'));
  const fixtureRoot = path.join(tempRoot, 'fixture');
  fs.mkdirSync(fixtureRoot, { recursive: true });
  fs.writeFileSync(path.join(fixtureRoot, 'real.txt'), 'ok');
  fs.symlinkSync('real.txt', path.join(fixtureRoot, 'link.txt'));

  const result = runBash(`
    set -euo pipefail
    export WOW_EVIDENCE_REPO_ROOT=${bashLiteral(tempRoot)}
    source ${JSON.stringify(publisherScriptPath)}
    temp_dir=$(mktemp -d)
    stage_selected_paths "$temp_dir" fixture
  `);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /publisher rejects symlinked files inside fixture: link\.txt/);
});

test('release evidence publisher manifest records sha256 and bytes for staged files', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-evidence-manifest-'));
  const stagedPath = path.join(tempRoot, 'nested');
  fs.mkdirSync(stagedPath, { recursive: true });
  fs.writeFileSync(path.join(stagedPath, 'alpha.txt'), 'alpha\n');
  fs.writeFileSync(path.join(tempRoot, 'root.txt'), 'beta');

  const result = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    write_release_manifest ${bashLiteral(tempRoot)} 2026-08-24-s2-evidence https://api.chickenbro.cloud/wow-evidence/releases
  `);
  assert.equal(result.status, 0, result.stderr);

  const manifest = JSON.parse(fs.readFileSync(path.join(tempRoot, 'release-manifest.json'), 'utf8'));
  assert.equal(manifest.schemaVersion, 1);
  assert.equal(manifest.releaseId, '2026-08-24-s2-evidence');
  assert.equal(manifest.immutableRoot, 'https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-evidence');
  assert.deepEqual(manifest.files, [
    {
      path: 'nested/alpha.txt',
      sha256: 'b6a98d9ce9a2d9149288fa3df42d377c3e42737afdcdaf714e33c0a100b51060',
      bytes: 6,
    },
    {
      path: 'root.txt',
      sha256: 'f44e64e75f3948e9f73f8dfa94721c4ce8cbb4f265c4790c702b2d41cfbf2753',
      bytes: 4,
    },
  ]);
  assert.equal(manifest.fileCount, 2);
  assert.equal(manifest.totalBytes, 10);
});

test('release evidence publisher enforces payload cap with a focused max-bytes override', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-evidence-cap-'));
  fs.writeFileSync(path.join(tempRoot, 'payload.txt'), '0123456789');

  const result = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    write_release_manifest ${bashLiteral(tempRoot)} 2026-08-24-s2-evidence https://api.chickenbro.cloud/wow-evidence/releases 8
  `);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /publisher payload exceeds 8 bytes: 10/);
});

test('release evidence publisher remote script fails on mv no-op conflict and cleans staging', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-evidence-remote-exec-'));
  const remoteRoot = path.join(tempRoot, 'remote-root');
  const fakeBin = path.join(tempRoot, 'bin');
  const payloadRoot = path.join(tempRoot, 'payload');
  const releaseId = '2026-08-24-s2-evidence';
  const releaseDir = path.join(remoteRoot, releaseId);
  fs.mkdirSync(fakeBin, { recursive: true });
  fs.mkdirSync(payloadRoot, { recursive: true });
  fs.mkdirSync(releaseDir, { recursive: true });
  fs.writeFileSync(path.join(releaseDir, 'existing.txt'), 'keep');
  fs.writeFileSync(path.join(payloadRoot, 'payload.txt'), 'payload');

  fs.writeFileSync(path.join(fakeBin, 'sudo'), '#!/usr/bin/env bash\nexec "$@"\n', { mode: 0o755 });
  fs.writeFileSync(path.join(fakeBin, 'mv'), `#!/usr/bin/env bash
set -euo pipefail
if [[ "\${1:-}" == '-Tn' ]]; then
  src="\${2:?}"
  dest="\${3:?}"
  if [[ -e "\${dest}" ]]; then
    exit 0
  fi
  python3 - "\${src}" "\${dest}" <<'PY'
import os
import shutil
import sys
src, dest = sys.argv[1:3]
os.replace(src, dest) if not os.path.isdir(src) else shutil.move(src, dest)
PY
  exit 0
fi
exec /bin/mv "$@"
`, { mode: 0o755 });

  const generated = runBash(`
    set -euo pipefail
    source ${JSON.stringify(publisherScriptPath)}
    build_remote_publish_script ${bashLiteral(remoteRoot)} ${bashLiteral(releaseId)}
  `);
  assert.equal(generated.status, 0, generated.stderr);

  const scriptPath = path.join(tempRoot, 'remote-script.sh');
  fs.writeFileSync(scriptPath, generated.stdout, { mode: 0o755 });

  const tarStream = spawnSync('tar', ['-C', payloadRoot, '-cf', '-', '.'], { encoding: null });
  assert.equal(tarStream.status, 0, tarStream.stderr?.toString?.() ?? '');

  const execution = spawnSync('bash', [scriptPath], {
    encoding: 'utf8',
    env: { ...process.env, PATH: `${fakeBin}:${process.env.PATH}` },
    input: tarStream.stdout,
  });
  assert.notEqual(execution.status, 0);
  assert.match(execution.stderr, /release-id already exists on remote host or lost create-only race/);
  const leftovers = fs.readdirSync(remoteRoot).filter((entry) => entry.startsWith(`.${releaseId}.tmp.`));
  assert.deepEqual(leftovers, []);
  assert.equal(fs.readFileSync(path.join(releaseDir, 'existing.txt'), 'utf8'), 'keep');
});
