const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const deployScript = fs.readFileSync(
  path.join(__dirname, '..', 'server', 'deploy_lighthouse.sh'),
  'utf8',
);

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
