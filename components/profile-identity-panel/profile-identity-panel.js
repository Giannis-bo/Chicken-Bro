const SYNC_LABELS = {
  local_only: '本地档案',
  syncing: '同步中',
  synced: '已同步',
  remote_failed: '同步受限',
  auth_required: '待登录',
  unknown: '来源参考'
}

const SYNC_STATES = {
  local_only: 'source_reference',
  syncing: 'loading',
  synced: 'verified',
  remote_failed: 'partial',
  auth_required: 'source_reference',
  unknown: 'source_reference'
}

const DRAFT_LABELS = {
  clean: '未修改',
  dirty: '待保存',
  saving: '保存中',
  saved: '已保存',
  failed: '保存失败'
}

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function normalizeSyncState(value) {
  const state = cleanText(value, 'local_only').toLowerCase()
  return Object.prototype.hasOwnProperty.call(SYNC_LABELS, state) ? state : 'unknown'
}

function normalizeDraftState(value) {
  const state = cleanText(value, 'clean').toLowerCase()
  return Object.prototype.hasOwnProperty.call(DRAFT_LABELS, state) ? state : 'clean'
}

function metricValue(metrics, key, fallback) {
  const value = metrics && metrics[key]
  if (value === 0 || value) return String(value)
  return fallback
}

function normalizeRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows.filter(Boolean).map((row, index) => ({
    key: cleanText(row.key || row.id, `profile-evidence-${index}`),
    iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
    label: cleanText(row.label, '证据'),
    value: cleanText(row.value || row.desc, '待读取'),
    status: cleanText(row.status || row.state, 'source_reference'),
    statusLabel: cleanText(row.statusLabel, '来源参考')
  }))
}

function normalizeAction(action, fallbackLabel, fallbackTone) {
  const data = action || {}
  return {
    key: cleanText(data.key || data.actionKey),
    label: cleanText(data.label, fallbackLabel),
    tone: cleanText(data.tone, fallbackTone || 'secondary'),
    disabled: Boolean(data.disabled),
    loading: Boolean(data.loading)
  }
}

function buildState(data) {
  const profile = data.profile || {}
  const metrics = data.metrics || {}
  const syncState = normalizeSyncState(data.syncState || profile.syncState)
  const draftState = normalizeDraftState(data.draftState || profile.draftState)
  const nickname = cleanText(data.nicknameDraft || profile.nickname, '点击填写微信昵称')
  const avatarUrl = cleanText(profile.avatarUrl)
  const evidenceRows = normalizeRows(data.evidenceRows)
  const visibleEvidenceRows = data.evidenceExpanded ? evidenceRows : evidenceRows.slice(0, 3)
  const isGuest = Boolean(profile.isGuest || syncState === 'local_only' || syncState === 'auth_required')
  return {
    rootClass: `state-${SYNC_STATES[syncState]} sync-${syncState} draft-${draftState}`,
    normalizedNickname: nickname,
    normalizedAvatarUrl: avatarUrl,
    normalizedAvatarFallback: cleanText(profile.fallbackText || nickname.slice(0, 1), 'W').slice(0, 2),
    normalizedRole: cleanText(profile.role || profile.roleLabel, isGuest ? '本地玩家' : '正式档案'),
    normalizedLoginState: cleanText(profile.loginState || profile.loginLabel, isGuest ? '本地优先' : '账号可用'),
    normalizedSyncState: syncState,
    normalizedSyncLabel: cleanText(data.syncLabel, SYNC_LABELS[syncState]),
    normalizedSyncVisual: SYNC_STATES[syncState],
    normalizedSyncGlyph: syncState === 'synced' ? 'OK' : syncState === 'remote_failed' ? '!' : syncState === 'syncing' ? '读' : '本',
    normalizedDraftState: draftState,
    normalizedDraftLabel: cleanText(data.draftLabel, DRAFT_LABELS[draftState]),
    normalizedMetricRows: [
      { key: 'talent', label: '天赋模板', value: metricValue(metrics, 'talentTemplateCount', '0') },
      { key: 'gear', label: '装备模板', value: metricValue(metrics, 'gearTemplateCount', '0') },
      { key: 'profile', label: '档案状态', value: cleanText(data.profileStatusLabel, SYNC_LABELS[syncState]) }
    ],
    normalizedEvidenceRows: visibleEvidenceRows,
    normalizedEvidenceSummary: evidenceRows.length ? `${visibleEvidenceRows.length}/${evidenceRows.length} 条证据` : '本地档案证据',
    normalizedPrimaryAction: normalizeAction(data.primaryAction, draftState === 'dirty' ? '保存资料' : '更新资料', 'primary'),
    normalizedLoginAction: normalizeAction(data.loginAction, '登录同步', 'secondary')
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    title: { type: String, value: '个人控制台' },
    meta: { type: String, value: '本地档案与模板同步' },
    profile: { type: Object, value: {} },
    nicknameDraft: { type: String, value: '' },
    draftState: { type: String, value: 'clean' },
    syncState: { type: String, value: 'local_only' },
    syncLabel: { type: String, value: '' },
    draftLabel: { type: String, value: '' },
    profileStatusLabel: { type: String, value: '' },
    metrics: { type: Object, value: {} },
    evidenceRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    primaryAction: { type: Object, value: {} },
    loginAction: { type: Object, value: {} },
    materialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    'profile, nicknameDraft, draftState, syncState, syncLabel, draftLabel, profileStatusLabel, metrics, evidenceRows, evidenceExpanded, primaryAction, loginAction': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleChooseAvatar() {
      this.triggerEvent('chooseavatar')
    },
    handleNicknameInput(event) {
      this.triggerEvent('updatenickname', {
        value: event.detail && event.detail.value
      })
    },
    handleNicknameConfirm() {
      this.triggerEvent('saveprofile')
    },
    handleSaveProfile() {
      this.triggerEvent('saveprofile')
    },
    handleLogin() {
      this.triggerEvent('login')
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle', {
        expanded: !this.data.evidenceExpanded
      })
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})
