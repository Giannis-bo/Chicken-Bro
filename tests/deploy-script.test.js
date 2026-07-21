const fs = require('node:fs')
const test = require('node:test')
const assert = require('node:assert/strict')
const { execFileSync, spawnSync } = require('node:child_process')

const scriptPath = 'server/deploy_lighthouse.sh'

function assertUsesMihomoProxy(service, unit) {
  assert.match(service, /After=.*mihomo\.service/, `${unit} must wait for mihomo when fetching external evidence`)
  assert.match(service, /Wants=.*mihomo\.service/, `${unit} must start mihomo when fetching external evidence`)
  assert.match(service, /Environment=HTTPS_PROXY=http:\/\/127\.0\.0\.1:7890/, `${unit} must proxy HTTPS`)
  assert.match(service, /Environment=HTTP_PROXY=http:\/\/127\.0\.0\.1:7890/, `${unit} must proxy HTTP`)
  assert.match(service, /Environment=ALL_PROXY=socks5h:\/\/127\.0\.0\.1:7890/, `${unit} must proxy non-HTTP clients`)
  assert.match(service, /Environment=NO_PROXY=127\.0\.0\.1,localhost/, `${unit} must keep local calls direct`)
  assert.match(service, /Environment=https_proxy=http:\/\/127\.0\.0\.1:7890/, `${unit} must proxy lowercase HTTPS clients`)
  assert.match(service, /Environment=http_proxy=http:\/\/127\.0\.0\.1:7890/, `${unit} must proxy lowercase HTTP clients`)
  assert.match(service, /Environment=all_proxy=socks5h:\/\/127\.0\.0\.1:7890/, `${unit} must proxy lowercase non-HTTP clients`)
  assert.match(service, /Environment=no_proxy=127\.0\.0\.1,localhost/, `${unit} must keep lowercase local calls direct`)
}

test('lighthouse deploy script supports a no-download hot deploy mode', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')

  const bashProbe = spawnSync(process.platform === 'win32' ? 'where.exe' : 'which', ['bash'], { stdio: 'ignore' })
  if (bashProbe.status === 0) {
    assert.doesNotThrow(() => execFileSync('bash', ['-n', scriptPath]))
  }
  assert.match(script, /WOW_DEPLOY_SKIP_BOOTSTRAP/)
  assert.match(script, /WOW_DEPLOY_START_ASYNC_SYNCS/)
  assert.match(script, /Skipping remote bootstrap/)
  assert.match(script, /Skipping PG-native async sync starts/)
  assert.match(script, /gzip on;/)
  assert.match(script, /gzip_types application\/json text\/plain text\/css application\/javascript;/)
  assert.match(script, /gzip_vary on;/)
  assert.match(script, /location \^~ \/wow-assets\/releases\//)
  assert.match(script, /root \/var\/www;/)
  assert.match(script, /try_files \$uri =404;/)
  assert.match(script, /Cache-Control "public, max-age=31536000, immutable"/)
  assert.match(script, /wow-stat-weights-sync\.service/)
  assert.match(script, /wow-stat-weights-sync\.timer/)
  assert.match(script, /wow-community-template-sync\.service/)
  assert.match(script, /wow-community-template-sync\.timer/)
  assert.match(script, /wow-season-recommended-gear-sync\.service/)
  assert.match(script, /wow-season-recommended-gear-sync\.timer/)
  assert.match(script, /wow-community-best-guard-sync\.service/)
  assert.match(script, /wow-community-best-guard-sync\.timer/)
  assert.match(script, /wow-recommended-bis-guard-sync\.service/)
  assert.match(script, /wow-recommended-bis-guard-sync\.timer/)
  assert.match(script, /wow-recommended-bis-prototype-sync\.service/)
  assert.match(script, /wow-data-health-followup\.service/)
  assert.match(script, /wow-data-health-followup\.timer/)
  assert.match(script, /wow-simc-runtime-update\.service/)
  assert.match(script, /sudo systemctl mask wow-news-backend\.service/)

  const skipBranch = script.indexOf('if [[ "${SKIP_BOOTSTRAP}" == "1" ]]')
  const bootstrapBranch = script.indexOf('else # full remote bootstrap')
  assert.ok(skipBranch >= 0, 'missing explicit hot deploy branch')
  assert.ok(bootstrapBranch > skipBranch, 'missing full bootstrap branch after hot deploy branch')

  for (const networkOrInstallCommand of [
    'sudo apt-get update',
    'https://chatgpt.com/codex/install.sh',
    'https://api.github.com/repos/{repo}/branches/{branch}',
    'https://github.com/${SIMC_GITHUB_REPO}/archive/${latest_simc_commit}.tar.gz',
    'sudo systemctl start wow-simc-version-check.service'
  ]) {
    const commandIndex = script.indexOf(networkOrInstallCommand)
    assert.ok(commandIndex > bootstrapBranch, `${networkOrInstallCommand} must stay out of hot deploy mode`)
  }
})

test('websim sync bypasses mihomo for Wago TraitEdge downloads', () => {
  const service = fs.readFileSync('server/wow-websim-sync.service', 'utf8')

  assert.match(service, /Environment=WOW_WAGO_DB2_BASE_URL=https:\/\/wago\.tools\/db2/)
  assert.match(service, /Environment=WOW_WAGO_DB2_TRAIT_EDGE_MAX_BYTES=8388608/)
  assert.match(service, /Environment=WOW_WAGO_DB2_TRAIT_EDGE_MAX_ROWS=50000/)
  assert.match(service, /Environment=WOW_WEBSIM_SIMC_MIN_PARENT_COVERAGE_PERCENT=80/)
  assert.match(service, /Environment=WOW_WEBSIM_SIMC_MIN_PROFILE_COVERAGE_PERCENT=80/)
  assert.match(service, /Environment=WOW_WEBSIM_SIMC_MIN_BASELINE_RETENTION_PERCENT=80/)
  assert.match(service, /Environment=NO_PROXY=[^\n]*wago\.tools/)
  assert.match(service, /Environment=no_proxy=[^\n]*wago\.tools/)
})

test('lighthouse deploy script enables PG-native sync timers in PG-only mode', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')
  const smokeIndex = script.indexOf('curl -fsS http://127.0.0.1/api/builds/home >/dev/null')
  assert.ok(smokeIndex > 0, 'missing builds home smoke check')
  const optInIndex = script.indexOf('if [[ "${START_ASYNC_SYNCS}" == "1" ]]')
  assert.ok(optInIndex > smokeIndex, 'async sync opt-in gate must run after API smoke checks')
  assert.match(script, /PG-native sync timers enabled/)

  for (const enableCommand of [
    'sudo systemctl enable --now wow-websim-sync.timer',
    'sudo systemctl enable --now wow-stat-weights-sync.timer',
    'sudo systemctl enable --now wow-community-template-sync.timer',
    'sudo systemctl enable --now wow-season-recommended-gear-sync.timer',
    'sudo systemctl enable --now wow-community-best-guard-sync.timer',
    'sudo systemctl enable --now wow-recommended-bis-guard-sync.timer',
    'sudo systemctl enable --now wow-data-health-followup.timer'
  ]) {
    const enableIndex = script.indexOf(enableCommand)
    assert.ok(enableIndex > 0 && enableIndex < smokeIndex, `${enableCommand} must run before API smoke checks`)
  }
  assert.doesNotMatch(script, /enable --now wow-gear-observed-backfill\.timer/)

  for (const startCommand of [
    'sudo systemctl start --no-block wow-websim-sync.service',
    'sudo systemctl start --no-block wow-stat-weights-sync.service',
    'sudo systemctl start --no-block wow-community-template-sync.service'
  ]) {
    const startIndex = script.indexOf(startCommand)
    assert.ok(startIndex > optInIndex, `${startCommand} must stay behind async sync opt-in`)
  }
  assert.doesNotMatch(script, /start --no-block wow-gear-observed-backfill\.service/)
})

test('gear release refresh timer is installed without deploy-triggered execution', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')
  const service = fs.readFileSync('server/wow-gear-release-refresh.service', 'utf8')
  const timer = fs.readFileSync('server/wow-gear-release-refresh.timer', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /flock -n \/run\/lock\/wow-gear-release-refresh\.lock/)
  assert.match(service, /ReadWritePaths=\/run\/lock/)
  assert.match(service, /ProtectHome=read-only/)
  assert.doesNotMatch(service, /ProtectHome=true/)
  assert.match(service, /python3 \/opt\/wow-mini-program\/server\/gear_release_refresh\.py --json/)
  assert.doesNotMatch(service, /curl|wget|HTTPS_PROXY|HTTP_PROXY/)
  assert.match(timer, /OnCalendar=\*-\*-\* 18:30:00/)
  assert.match(timer, /RandomizedDelaySec=15min/)
  assert.match(timer, /Persistent=true/)

  assert.match(script, /wow-gear-release-refresh\.service/)
  assert.match(script, /wow-gear-release-refresh\.timer/)
  assert.match(script, /sudo systemctl enable wow-gear-release-refresh\.timer/)
  assert.doesNotMatch(script, /enable --now wow-gear-release-refresh\.timer/)
  assert.doesNotMatch(script, /systemctl start (?:--no-block )?wow-gear-release-refresh\.service/)
})

test('winner attribute audit is detached from release refresh and never deploy-started', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')
  const refresh = fs.readFileSync('server/wow-gear-release-refresh.service', 'utf8')
  const audit = fs.readFileSync('server/wow-attribute-rule-audit.service', 'utf8')

  assert.match(refresh, /^OnSuccess=wow-attribute-rule-audit\.service$/m)
  assert.match(audit, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(audit, /Environment=WOW_ATTRIBUTE_RULE_AUDIT_MAX_JOBS=1/)
  assert.match(audit, /flock -n \/run\/lock\/wow-attribute-rule-audit\.lock/)
  assert.match(audit, /python3 \/opt\/wow-mini-program\/server\/attribute_rule_audit_worker\.py --json/)
  assert.match(audit, /ReadWritePaths=\/run\/lock/)
  assert.match(audit, /ProtectHome=read-only/)
  assert.doesNotMatch(audit, /SIMC_GITHUB_REPO|simc_runtime_update|gear_stat_snapshot_worker/)
  assertUsesMihomoProxy(audit, 'server/wow-attribute-rule-audit.service')

  assert.match(script, /wow-attribute-rule-audit\.service/)
  assert.doesNotMatch(script, /enable(?: --now)? wow-attribute-rule-audit\.service/)
  assert.doesNotMatch(script, /systemctl start (?:--no-block )?wow-attribute-rule-audit\.service/)
})

test('recommended bis guard sync has a daily readiness-only systemd timer', () => {
  const service = fs.readFileSync('server/wow-recommended-bis-guard-sync.service', 'utf8')
  const timer = fs.readFileSync('server/wow-recommended-bis-guard-sync.timer', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 900 \/run\/lock\/wow-mini-program-bis-guard\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/recommended_bis_guard_sync\.py/)
  assert.match(service, /TimeoutStartSec=5min/)
  assert.doesNotMatch(service, /curl|wget|github\.com|SIMC_GITHUB_REPO|WOW_NEWS_DB/)
  assert.match(timer, /OnBootSec=35min/)
  assert.match(timer, /OnCalendar=\*-\*-\* 08:10:00/)
  assert.match(timer, /RandomizedDelaySec=15min/)
  assert.match(timer, /Persistent=true/)
})

test('recommended bis prototype sync is a manual PG-only projected-template service', () => {
  const service = fs.readFileSync('server/wow-recommended-bis-prototype-sync.service', 'utf8')
  const script = fs.readFileSync('server/recommended_bis_prototype_sync.py', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 1800 \/run\/lock\/wow-mini-program-bis-prototype\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/recommended_bis_prototype_sync\.py/)
  assert.match(service, /TimeoutStartSec=45min/)
  assert.doesNotMatch(service, /curl|wget|github\.com|SIMC_GITHUB_REPO|WOW_NEWS_DB/)
  assert.match(script, /sync_recommended_bis_prototype_postgres/)
  assert.doesNotMatch(script, /curl|wget|urlopen|requests|SIMC_GITHUB_REPO/)
})

test('community best guard sync has a daily readiness-only systemd timer', () => {
  const service = fs.readFileSync('server/wow-community-best-guard-sync.service', 'utf8')
  const timer = fs.readFileSync('server/wow-community-best-guard-sync.timer', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 900 \/run\/lock\/wow-mini-program-community-best-guard\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/community_best_guard_sync\.py/)
  assert.match(service, /TimeoutStartSec=5min/)
  assert.doesNotMatch(service, /curl|wget|github\.com|SIMC_GITHUB_REPO|WOW_NEWS_DB/)
  assert.match(timer, /OnBootSec=30min/)
  assert.match(timer, /OnCalendar=\*-\*-\* 08:00:00/)
  assert.match(timer, /RandomizedDelaySec=15min/)
  assert.match(timer, /Persistent=true/)
})

test('season recommended gear sync has a daily persistent systemd timer', () => {
  const service = fs.readFileSync('server/wow-season-recommended-gear-sync.service', 'utf8')
  const timer = fs.readFileSync('server/wow-season-recommended-gear-sync.timer', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 7200 \/run\/lock\/wow-mini-program-sync\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/season_recommended_gear_sync\.py/)
  assert.match(service, /TimeoutStartSec=45min/)
  assert.doesNotMatch(service, /WOW_NEWS_DB/)
  assert.match(timer, /OnBootSec=20min/)
  assert.match(timer, /OnCalendar=\*-\*-\* 07:30:00/)
  assert.match(timer, /RandomizedDelaySec=20min/)
  assert.match(timer, /Persistent=true/)
})

test('data health followup triggers safe blocker continuation through existing units', () => {
  const service = fs.readFileSync('server/wow-data-health-followup.service', 'utf8')
  const timer = fs.readFileSync('server/wow-data-health-followup.timer', 'utf8')

  assert.match(service, /ExecStart=\/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/data_health_followup\.py --execute/)
  assert.doesNotMatch(service, /SIMC_GITHUB_REPO|github\.com|curl|wget/)
  assert.match(timer, /OnBootSec=25min/)
  assert.match(timer, /OnUnitActiveSec=2h/)
  assert.match(timer, /RandomizedDelaySec=10min/)
  assert.match(timer, /Persistent=true/)
})

test('talent graph recovery is a manually triggered SimC and TraitEdge-only unit', () => {
  const recoveryUnit = fs.readFileSync('server/wow-talent-graph-recovery.service', 'utf8')
  const deployScript = fs.readFileSync(scriptPath, 'utf8')

  assert.match(recoveryUnit, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(recoveryUnit, /Environment=WOW_WEBSIM_SKIP_BLIZZARD=1/)
  assert.match(recoveryUnit, /Environment=WOW_WEBSIM_SKIP_RAIDERIO=1/)
  assert.match(recoveryUnit, /Environment=WOW_WEBSIM_FETCH_WAGO_DB2_TRAIT_EDGE=1/)
  assert.match(recoveryUnit, /ExecStart=\/usr\/bin\/flock -w 7200 \/run\/lock\/wow-mini-program-sync\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/websim_sync\.py/)
  assertUsesMihomoProxy(recoveryUnit, 'server/wow-talent-graph-recovery.service')
  assert.match(deployScript, /wow-talent-graph-recovery\.service/)
  assert.doesNotMatch(deployScript, /systemctl start (?:--no-block )?wow-talent-graph-recovery\.service/)
})

test('simc runtime update has a locked systemd service and reusable updater', () => {
  assert.ok(fs.existsSync('server/wow-simc-runtime-update.service'), 'missing simc runtime update service')
  assert.ok(fs.existsSync('server/simc_runtime_update.sh'), 'missing simc runtime update script')

  const service = fs.readFileSync('server/wow-simc-runtime-update.service', 'utf8')
  const script = fs.readFileSync('server/simc_runtime_update.sh', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /Environment=SIMC_GITHUB_REPO=simulationcraft\/simc/)
  assert.match(service, /Environment=SIMC_BRANCH=midnight/)
  assertUsesMihomoProxy(service, 'server/wow-simc-runtime-update.service')
  assert.match(service, /Environment=NO_PROXY=[^\n]*api\.github\.com[^\n]*codeload\.github\.com/)
  assert.match(service, /Environment=no_proxy=[^\n]*api\.github\.com[^\n]*codeload\.github\.com/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 21600 \/run\/lock\/wow-mini-program-sync\.lock \/opt\/wow-mini-program\/server\/simc_runtime_update\.sh/)
  assert.match(service, /TimeoutStartSec=480min/)
  assert.doesNotMatch(service, /WOW_NEWS_DB/)

  assert.match(script, /https:\/\/api\.github\.com\/repos\/\$\{repo\}\/branches\/\$\{branch\}/)
  assert.match(script, /https:\/\/codeload\.github\.com\/\$\{repo\}\/tar\.gz\/\$\{latest_simc_commit\}/)
  assert.match(script, /cmake -S "\$\{SIMC_SRC\}" -B "\$\{SIMC_BUILD\}"/)
  assert.match(script, /wow-simc-version-check/)
})

test('simc version check unit generated by deploy also uses mihomo proxy', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')
  const serviceStart = script.indexOf('Description=Check SimulationCraft source version')
  const serviceEnd = script.indexOf('SIMCSERVICE', serviceStart)

  assert.ok(serviceStart > 0, 'missing generated SimC version check service')
  assert.ok(serviceEnd > serviceStart, 'missing end of generated SimC version check service')
  assertUsesMihomoProxy(script.slice(serviceStart, serviceEnd), 'generated wow-simc-version-check.service')
})

test('external evidence fetch units use the local mihomo proxy', () => {
  for (const unit of [
    'server/wow-backend.service',
    'server/wow-websim-sync.service',
    'server/wow-stat-weights-sync.service',
    'server/wow-community-template-sync.service',
    'server/wow-gear-observed-backfill.service',
    'server/wow-attribute-rule-audit.service',
    'server/wow-talent-graph-recovery.service',
    'server/wow-simc-runtime-update.service'
  ]) {
    assertUsesMihomoProxy(fs.readFileSync(unit, 'utf8'), unit)
  }
})

test('news refresh cron defaults to the unified deployment log path and long timeout', () => {
  const script = fs.readFileSync('server/refresh_cron.sh', 'utf8')

  assert.match(script, /WOW_NEWS_REFRESH_URL:-http:\/\/127\.0\.0\.1:8787\/api\/news\/refresh\?mode=scheduled&scope=queue&limit=1/)
  assert.match(script, /WOW_NEWS_REFRESH_LOG:-\/opt\/wow-mini-program\/logs\/refresh_cron\.log/)
  assert.match(script, /WOW_NEWS_REFRESH_TIMEOUT:-240/)
  assert.doesNotMatch(script, /WOW_NEWS_REFRESH_URL:-http:\/\/127\.0\.0\.1\/api\/news\/refresh/)
  assert.doesNotMatch(script, /wow-news-backend\/logs\/refresh_cron\.log/)
  assert.doesNotMatch(script, /WOW_NEWS_REFRESH_TIMEOUT:-45/)
})

test('community template sync has a daily incremental persistent systemd timer', () => {
  const service = fs.readFileSync('server/wow-community-template-sync.service', 'utf8')
  const timer = fs.readFileSync('server/wow-community-template-sync.timer', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.match(service, /Environment=WOW_COMMUNITY_TEMPLATE_SYNC_MODE=daily_incremental/)
  assert.match(service, /Environment=WOW_COMMUNITY_DAILY_TIER=daily_targeted/)
  assert.match(service, /Environment=WOW_COMMUNITY_DAILY_TALENT_MODE=missing_slots/)
  assert.match(service, /Environment=WOW_COMMUNITY_DAILY_GEAR_MODE=gear_template_targeted_refresh/)
  assert.match(service, /Environment=WOW_COMMUNITY_DAILY_GEAR_SKIP_WHEN_NO_TARGETS=1/)
  assert.match(service, /Environment=WOW_COMMUNITY_DAILY_GEAR_REFRESH_RAIDERIO=1/)
  assert.match(service, /Environment=WOW_RAIDERIO_REGIONS=cn,tw,kr,us,eu/)
  assert.match(service, /Environment=WOW_RAIDERIO_SPEC_RANKING_ENABLED=1/)
  assert.match(service, /Environment=WOW_RAIDERIO_SPEC_RANKING_REGIONS=world/)
  assert.match(service, /Environment=WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE=50/)
  assert.match(service, /Environment=WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_ENABLED=1/)
  assert.match(service, /Environment=WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_PAGES=1/)
  assert.match(service, /Environment=WOW_RAIDERIO_RUN_DETAIL_LIMIT=160/)
  assert.match(service, /Environment=WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC=4/)
  assert.match(service, /Environment=WOW_COMMUNITY_TEMPLATE_TARGETED_RUN_DETAIL_LIMIT=240/)
  assert.match(service, /Environment=WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_LIMIT=160/)
  assert.match(service, /Environment=WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_LIMIT_PER_SPEC=4/)
  assert.match(service, /Environment=WOW_RAIDERIO_COMMUNITY_TEMPLATE_LIMIT=240/)
  assert.match(service, /Environment=NO_PROXY=[^\n]*raider\.io/)
  assert.match(service, /Environment=no_proxy=[^\n]*raider\.io/)
  assert.match(service, /Environment=WOW_COMMUNITY_GEAR_FIRST_SYNC_SPEC_LIMIT=8/)
  assert.match(service, /Environment=WOW_COMMUNITY_GEAR_FIRST_SYNC_PROFILE_LIMIT=160/)
  assert.match(service, /Environment=WOW_COMMUNITY_GEAR_FIRST_SYNC_ITEM_PROBE_LIMIT=96/)
  assert.match(service, /MemoryHigh=768M/)
  assert.match(service, /MemoryMax=1024M/)
  assert.doesNotMatch(service, /Environment=WOW_RAIDERIO_RUN_PAGES=8/)
  assert.doesNotMatch(service, /Environment=WOW_RAIDERIO_RUN_DETAIL_LIMIT=1400/)
  assert.doesNotMatch(service, /WOW_NEWS_DB/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 7200 \/run\/lock\/wow-mini-program-sync\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/community_template_sync\.py/)
  assert.match(service, /TimeoutStartSec=180min/)
  assert.match(timer, /OnBootSec=12min/)
  assert.match(timer, /OnCalendar=\*-\*-\* 06:15:00/)
  assert.match(timer, /RandomizedDelaySec=30min/)
  assert.doesNotMatch(timer, /OnUnitActiveSec=6h/)
  assert.match(timer, /Persistent=true/)
})

test('production systemd units do not configure SQLite runtime paths', () => {
  for (const unit of [
    'server/wow-backend.service',
    'server/wow-websim-sync.service',
    'server/wow-stat-weights-sync.service',
    'server/wow-community-template-sync.service',
    'server/wow-gear-observed-backfill.service',
    'server/wow-season-recommended-gear-sync.service',
    'server/wow-recommended-bis-prototype-sync.service',
    'server/wow-data-health-followup.service',
    'server/wow-talent-graph-recovery.service',
    'server/wow-simc-runtime-update.service'
  ]) {
    const service = fs.readFileSync(unit, 'utf8')
    assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/, `${unit} must opt into PG-only runtime`)
    assert.doesNotMatch(service, /WOW_NEWS_DB/, `${unit} must not configure WOW_NEWS_DB`)
    assert.doesNotMatch(service, /server\/data\/wow_news\.sqlite3/, `${unit} must not pass the runtime SQLite file`)
  }
})
