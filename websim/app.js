;(function (root) {
  const state = {
    classes: [],
    scenarios: [],
    gearSlots: [],
    instances: [],
    loot: [],
    selectedInstanceId: '',
    selectedEncounterId: '',
    classKey: 'mage',
    specKey: 'arcane',
    scenarioKey: 'single',
    talents: [],
    selectedTalents: new Set(),
    gear: {},
    presets: [],
    currentSeason: null,
    dataStatus: 'blocked'
  }

  const slotLabels = {
    head: '头部',
    neck: '颈部',
    shoulder: '肩部',
    back: '背部',
    chest: '胸部',
    wrists: '腕部',
    hands: '手部',
    waist: '腰部',
    legs: '腿部',
    feet: '脚部',
    finger1: '戒指 1',
    finger2: '戒指 2',
    trinket1: '饰品 1',
    trinket2: '饰品 2',
    main_hand: '主手',
    off_hand: '副手'
  }

  function $(id) {
    return root.document ? root.document.getElementById(id) : null
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function storageGet(key) {
    try {
      return root.localStorage && root.localStorage.getItem(key)
    } catch (error) {
      return ''
    }
  }

  function storageSet(key, value) {
    try {
      root.localStorage && root.localStorage.setItem(key, value)
    } catch (error) {
      // Analytics must never block the simulator.
    }
  }

  function randomAnalyticsId(prefix) {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  }

  function analyticsClientId() {
    const key = 'wow_analytics_client_id'
    const stored = storageGet(key)
    if (stored) return stored
    const next = randomAnalyticsId('web')
    storageSet(key, next)
    return next
  }

  function analyticsSessionId() {
    const key = 'wow_analytics_session_id'
    const startedKey = 'wow_analytics_session_started_at'
    const stored = storageGet(key)
    const startedAt = Number(storageGet(startedKey) || 0)
    if (stored && startedAt && Date.now() - startedAt < 30 * 60 * 1000) return stored
    const next = randomAnalyticsId('session')
    storageSet(key, next)
    storageSet(startedKey, String(Date.now()))
    return next
  }

  function trackWebsimEvent(eventName, properties) {
    if (!root.fetch || !/^[a-z][a-z0-9_]{0,79}$/.test(eventName || '')) return
    const clientId = analyticsClientId()
    const sessionId = analyticsSessionId()
    root.fetch('/api/analytics/events', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Wow-Client-Id': clientId,
        'X-Wow-Session-Id': sessionId,
        'X-Wow-Platform': 'websim'
      },
      body: JSON.stringify({
        clientId,
        sessionId,
        platform: 'websim',
        events: [
          {
            eventId: `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`,
            eventName,
            occurredAt: new Date().toISOString(),
            page: '/websim',
            properties: properties || {}
          }
        ]
      })
    }).catch(() => {})
  }

  async function apiJson(path, options) {
    const response = await root.fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    })
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`)
    }
    return response.json()
  }

  function classByKey(key) {
    return state.classes.find((item) => item.key === key) || state.classes[0] || { specs: [] }
  }

  function applyInitialSelection(selection) {
    const preferredClass = state.classes.find((item) => item.key === selection.classKey) || classByKey(state.classKey)
    state.classKey = preferredClass.key || state.classKey
    const specs = preferredClass.specs || []
    const preferredSpec = specs.find((item) => item.key === selection.specKey) || specs.find((item) => item.key === state.specKey) || specs[0]
    state.specKey = (preferredSpec && preferredSpec.key) || state.specKey
  }

  function selectedSpecLabel() {
    const klass = classByKey(state.classKey)
    const spec = (klass.specs || []).find((item) => item.key === state.specKey)
    return `${klass.label || state.classKey} ${spec ? spec.label : state.specKey}`
  }

  function normalizeGearItem(item) {
    const id = item && (item.itemId || item.item_id || item.id)
    const slot = item && (item.slot || item.slotKey)
    if (!id || !slot) return null
    return {
      slot,
      id: String(id),
      itemId: String(id),
      name: item.name || `物品 ${id}`,
      iconUrl: item.iconUrl || '',
      ilevel: item.ilevel || item.itemLevel || '',
      bonus_id: item.bonus_id || item.bonusId || '',
      gem_id: item.gem_id || item.gemId || '',
      enchant_id: item.enchant_id || item.enchantId || ''
    }
  }

  function pairedSlot(slot) {
    if (slot === 'finger1' && state.gear.finger1) return 'finger2'
    if (slot === 'trinket1' && state.gear.trinket1) return 'trinket2'
    return slot
  }

  function addGearItem(item) {
    const normalized = normalizeGearItem(item)
    if (!normalized) return
    normalized.slot = pairedSlot(normalized.slot)
    state.gear[normalized.slot] = normalized
    trackWebsimEvent('websim_gear_add', {
      classKey: state.classKey,
      specKey: state.specKey,
      slot: normalized.slot,
      itemId: normalized.itemId || normalized.id || ''
    })
    renderGear()
    renderProfilePreview()
  }

  function filterLootRows(items, filters) {
    const query = String((filters && filters.q) || '').trim().toLowerCase()
    return (items || []).filter((item) => {
      if (filters && filters.instanceId && item.instanceId !== filters.instanceId) return false
      if (filters && filters.encounterId && item.encounterId !== filters.encounterId) return false
      if (filters && filters.slot && item.slot !== filters.slot) return false
      if (!query) return true
      return [item.name, item.instanceName, item.encounterName, item.itemId]
        .some((value) => String(value || '').toLowerCase().includes(query))
    })
  }

  function buildProfilePayload() {
    return {
      classKey: state.classKey,
      specKey: state.specKey,
      scenarioKey: state.scenarioKey,
      talents: $('talentInput') ? $('talentInput').value.trim() : '',
      gearSelection: {
        items: Object.values(state.gear).filter(Boolean)
      },
      saveTask: true,
      guestId: getGuestId()
    }
  }

  function getGuestId() {
    try {
      const key = 'wow_websim_guest_id'
      let value = root.localStorage && root.localStorage.getItem(key)
      if (!value) {
        value = `websim-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
        root.localStorage && root.localStorage.setItem(key, value)
      }
      return value
    } catch (error) {
      return 'websim-guest'
    }
  }

  function renderSelectors() {
    const classSelect = $('classSelect')
    const specSelect = $('specSelect')
    const scenarioSelect = $('scenarioSelect')
    if (!classSelect || !specSelect || !scenarioSelect) return
    classSelect.innerHTML = state.classes.map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)}</option>`
    ).join('')
    classSelect.value = state.classKey
    const klass = classByKey(state.classKey)
    specSelect.innerHTML = (klass.specs || []).map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)}</option>`
    ).join('')
    specSelect.value = state.specKey
    scenarioSelect.innerHTML = state.scenarios.map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.title)}</option>`
    ).join('')
    scenarioSelect.value = state.scenarioKey
    const label = $('characterLabel')
    if (label) label.textContent = selectedSpecLabel()
  }

  function renderTalents() {
    const tree = $('talentTree')
    if (!tree) return
    if (state.dataStatus !== 'verified') {
      tree.innerHTML = '<div class="blocked-state">赛季数据尚未通过暴雪官方 API 校验，暂不展示可能过期的天赋树。</div>'
      return
    }
    if (!state.talents.length) {
      tree.innerHTML = '<div class="blocked-state">天赋图标和说明仍在同步中，校验完成后会显示中文版天赋树。</div>'
      return
    }
    tree.innerHTML = state.talents.map((node) => {
      const selected = state.selectedTalents.has(node.id) || node.selected
      const col = Math.max(1, Number(node.col || 1))
      const row = Math.max(1, Number(node.row || 1))
      return `<button class="talent-node ${selected ? 'selected' : ''}" data-id="${escapeHtml(node.id)}" style="grid-column:${col};grid-row:${row}">
        ${node.iconUrl ? `<img class="talent-icon" src="${escapeHtml(node.iconUrl)}" alt="">` : `<span class="talent-rank">${escapeHtml(node.rank || 1)}</span>`}
        <span class="talent-name" title="${escapeHtml(node.description || '')}">${escapeHtml(node.name)}</span>
      </button>`
    }).join('')
    tree.querySelectorAll('.talent-node').forEach((button) => {
      button.addEventListener('click', () => {
        const id = button.dataset.id
        if (state.selectedTalents.has(id)) state.selectedTalents.delete(id)
        else state.selectedTalents.add(id)
        trackWebsimEvent('websim_talent_toggle', {
          classKey: state.classKey,
          specKey: state.specKey,
          talentId: id,
          selected: state.selectedTalents.has(id)
        })
        renderTalents()
      })
    })
  }

  function gearSlotHtml(slot) {
    const item = state.gear[slot]
    const icon = item && item.iconUrl ? `<img class="slot-icon" src="${escapeHtml(item.iconUrl)}" alt="">` : '<div class="slot-icon"></div>'
    return `<button class="gear-slot" data-slot="${escapeHtml(slot)}">
      ${icon}
      <span class="slot-copy">
        <p class="${item ? 'slot-name' : 'slot-empty'}">${escapeHtml(item ? item.name : slotLabels[slot] || slot)}</p>
        <p class="slot-empty">${escapeHtml(item ? `物品 ID=${item.itemId || item.id}` : '空栏位')}</p>
      </span>
      <span class="slot-meta">${escapeHtml(slotLabels[slot] || slot)}</span>
    </button>`
  }

  function renderGear() {
    const left = $('leftSlots')
    const right = $('rightSlots')
    const count = $('selectedCount')
    if (!left || !right) return
    const split = Math.ceil(state.gearSlots.length / 2)
    left.innerHTML = state.gearSlots.slice(0, split).map(gearSlotHtml).join('')
    right.innerHTML = state.gearSlots.slice(split).map(gearSlotHtml).join('')
    ;[left, right].forEach((column) => {
      column.querySelectorAll('.gear-slot').forEach((button) => {
        button.addEventListener('click', () => {
          const item = state.gear[button.dataset.slot]
          delete state.gear[button.dataset.slot]
          if (item) {
            trackWebsimEvent('websim_gear_remove', {
              classKey: state.classKey,
              specKey: state.specKey,
              slot: button.dataset.slot,
              itemId: item.itemId || item.id || ''
            })
          }
          renderGear()
          renderProfilePreview()
        })
      })
    })
    if (count) count.textContent = String(Object.keys(state.gear).length)
  }

  function renderJournal() {
    const instanceList = $('instanceList')
    const encounterList = $('encounterList')
    const lootList = $('lootList')
    if (!instanceList || !encounterList || !lootList) return
    if (state.dataStatus !== 'verified') {
      instanceList.innerHTML = '<div class="blocked-state">当前赛季未验证</div>'
      encounterList.innerHTML = '<div class="blocked-state">等待同步</div>'
      lootList.innerHTML = '<div class="blocked-state">为避免显示上赛季掉落，装备查询会在官方赛季数据校验后开放。</div>'
      return
    }
    instanceList.innerHTML = state.instances.map((instance) =>
      `<button class="journal-row ${instance.id === state.selectedInstanceId ? 'active' : ''}" data-id="${escapeHtml(instance.id)}">${escapeHtml(instance.name)}</button>`
    ).join('')
    const selectedInstance = state.instances.find((item) => item.id === state.selectedInstanceId) || state.instances[0]
    const encounters = selectedInstance ? selectedInstance.encounters || [] : []
    encounterList.innerHTML = encounters.map((encounter) =>
      `<button class="journal-row ${encounter.id === state.selectedEncounterId ? 'active' : ''}" data-id="${escapeHtml(encounter.id)}">${escapeHtml(encounter.name)}</button>`
    ).join('')
    const query = $('lootSearch') ? $('lootSearch').value : ''
    const visibleLoot = filterLootRows(state.loot, {
      instanceId: state.selectedInstanceId,
      encounterId: state.selectedEncounterId,
      q: query
    })
    lootList.innerHTML = visibleLoot.map((item) => {
      const icon = item.iconUrl ? `<img class="loot-icon" src="${escapeHtml(item.iconUrl)}" alt="">` : '<div class="loot-icon"></div>'
      return `<button class="loot-row" data-item-id="${escapeHtml(item.itemId)}">
        ${icon}
        <span class="loot-copy">
          <p class="loot-name">${escapeHtml(item.name)}</p>
          <p class="loot-source">${escapeHtml(item.encounterName)} · ${escapeHtml(item.instanceName)}</p>
        </span>
        <span class="loot-meta">${escapeHtml(item.slot || '物品')}</span>
      </button>`
    }).join('')
    instanceList.querySelectorAll('.journal-row').forEach((button) => {
      button.addEventListener('click', () => {
        state.selectedInstanceId = button.dataset.id
        const instance = state.instances.find((item) => item.id === state.selectedInstanceId)
        state.selectedEncounterId = ((instance && instance.encounters) || [])[0]?.id || ''
        renderJournal()
      })
    })
    encounterList.querySelectorAll('.journal-row').forEach((button) => {
      button.addEventListener('click', () => {
        state.selectedEncounterId = button.dataset.id
        renderJournal()
      })
    })
    lootList.querySelectorAll('.loot-row').forEach((button) => {
      button.addEventListener('click', () => {
        const item = visibleLoot.find((row) => String(row.itemId) === String(button.dataset.itemId))
        addGearItem(item)
      })
    })
  }

  async function loadTalents() {
    const payload = await apiJson(`/api/websim/talents?class=${encodeURIComponent(state.classKey)}&spec=${encodeURIComponent(state.specKey)}`)
    state.currentSeason = payload.currentSeason || state.currentSeason
    state.dataStatus = payload.dataStatus || state.dataStatus
    state.talents = payload.nodes || []
    state.presets = payload.presets || []
    state.selectedTalents = new Set((state.talents || []).filter((node) => node.selected).map((node) => node.id))
    renderTalents()
  }

  async function loadGear() {
    const payload = await apiJson(`/api/websim/gear?class=${encodeURIComponent(state.classKey)}&spec=${encodeURIComponent(state.specKey)}`)
    state.currentSeason = payload.currentSeason || state.currentSeason
    state.dataStatus = payload.dataStatus || state.dataStatus
    state.gearSlots = payload.slots || state.gearSlots
    renderGear()
  }

  async function loadLoot() {
    const payload = await apiJson('/api/websim/loot')
    state.currentSeason = payload.currentSeason || state.currentSeason
    state.dataStatus = payload.dataStatus || state.dataStatus
    state.instances = payload.instances || []
    state.loot = payload.items || []
    state.selectedInstanceId = state.selectedInstanceId || (state.instances[0] && state.instances[0].id) || ''
    const instance = state.instances.find((item) => item.id === state.selectedInstanceId) || state.instances[0]
    state.selectedEncounterId = state.selectedEncounterId || (((instance && instance.encounters) || [])[0] && instance.encounters[0].id) || ''
    renderJournal()
  }

  function renderGateNotice() {
    const notice = $('gateNotice')
    const seasonStatus = $('seasonStatus')
    const season = state.currentSeason || {}
    const label = season.seasonLabel || season.label || '赛季未验证'
    if (seasonStatus) seasonStatus.textContent = state.dataStatus === 'verified' ? `当前赛季：${label}` : '赛季数据未验证'
    if (!notice) return
    if (state.dataStatus === 'verified') {
      notice.textContent = `已绑定 ${label}，版本 ${season.seasonRevision || season.revision || 'verified'}`
      notice.classList.remove('blocked')
    } else {
      const errors = Array.isArray(season.errors) && season.errors.length ? `：${season.errors[0]}` : ''
      notice.textContent = `赛季数据同步中，暂不展示可能过期的副本、装备和天赋${errors}`
      notice.classList.add('blocked')
    }
  }

  function renderProfilePreview(profile) {
    const preview = $('profilePreview')
    if (!preview) return
    if (profile) {
      preview.textContent = profile
      return
    }
    const payload = buildProfilePayload()
    const lines = [
      `${payload.classKey}="WebSim_${payload.specKey}"`,
      `spec=${payload.specKey}`,
      'level=90',
      payload.talents ? `talents=${payload.talents}` : '# talents=',
      ...payload.gearSelection.items.map((item) => `${item.slot}=${item.name},id=${item.itemId || item.id}`)
    ]
    preview.textContent = lines.join('\n')
  }

  async function generateProfile() {
    trackWebsimEvent('websim_profile_generate', {
      classKey: state.classKey,
      specKey: state.specKey,
      selectedGearCount: Object.keys(state.gear).length
    })
    const result = await apiJson('/api/websim/profile', {
      method: 'POST',
      body: JSON.stringify(buildProfilePayload())
    })
    renderProfilePreview(result.profile || '')
    return result.profile
  }

  async function simulate() {
    const resultBox = $('simulationResult')
    if (resultBox) resultBox.textContent = 'SimC 模拟运行中...'
    trackWebsimEvent('websim_simulate_submit', {
      classKey: state.classKey,
      specKey: state.specKey,
      scenarioKey: state.scenarioKey,
      selectedGearCount: Object.keys(state.gear).length
    })
    const result = await apiJson('/api/websim/simulate', {
      method: 'POST',
      body: JSON.stringify(buildProfilePayload())
    })
    const dps = result.simulation && result.simulation.metrics && result.simulation.metrics.dps
    if (resultBox) {
      resultBox.innerHTML = dps
        ? `<strong>${escapeHtml(dps)} DPS</strong><span>${escapeHtml(result.status || '已完成')}</span>`
        : `<strong>${result.simulation && result.simulation.ran ? '已完成' : '已阻断'}</strong><span>${escapeHtml((result.simulation && result.simulation.error) || result.status || '未解析到 DPS')}</span>`
    }
    if (result.request && result.request.profile) renderProfilePreview(result.request.profile)
    trackWebsimEvent('websim_simulate_result', {
      classKey: state.classKey,
      specKey: state.specKey,
      scenarioKey: state.scenarioKey,
      simulationRan: !!(result.simulation && result.simulation.ran),
      taskId: result.taskId || '',
      hasDps: !!dps
    })
    return result
  }

  function bindEvents() {
    $('classSelect')?.addEventListener('change', async (event) => {
      state.classKey = event.target.value
      const klass = classByKey(state.classKey)
      state.specKey = ((klass.specs || [])[0] || {}).key || state.specKey
      trackWebsimEvent('websim_class_change', { classKey: state.classKey, specKey: state.specKey })
      renderSelectors()
      await Promise.all([loadTalents(), loadGear()])
      renderProfilePreview()
    })
    $('specSelect')?.addEventListener('change', async (event) => {
      state.specKey = event.target.value
      trackWebsimEvent('websim_spec_change', { classKey: state.classKey, specKey: state.specKey })
      renderSelectors()
      await Promise.all([loadTalents(), loadGear()])
      renderProfilePreview()
    })
    $('scenarioSelect')?.addEventListener('change', (event) => {
      state.scenarioKey = event.target.value
      renderProfilePreview()
    })
    $('talentInput')?.addEventListener('input', renderProfilePreview)
    $('lootSearch')?.addEventListener('input', renderJournal)
    $('profileButton')?.addEventListener('click', () => generateProfile().catch(showError))
    $('simulateButton')?.addEventListener('click', () => simulate().catch(showError))
    $('clearGearButton')?.addEventListener('click', () => {
      state.gear = {}
      renderGear()
      renderProfilePreview()
    })
    $('loadPresetButton')?.addEventListener('click', () => {
      const preset = state.presets[0]
      if (preset && preset.profile) renderProfilePreview(preset.profile)
    })
    root.document.querySelectorAll('.tab-button').forEach((button) => {
      button.addEventListener('click', () => {
        trackWebsimEvent('websim_tab_switch', { tab: button.dataset.tab || '' })
        root.document.querySelectorAll('.tab-button').forEach((item) => item.classList.toggle('active', item === button))
        root.document.querySelectorAll('.workspace-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `${button.dataset.tab}Panel`))
      })
    })
  }

  function showError(error) {
    const resultBox = $('simulationResult')
    if (resultBox) resultBox.innerHTML = `<strong>错误</strong><span>${escapeHtml(error.message || error)}</span>`
  }

  async function init() {
    if (!root.document) return
    bindEvents()
    trackWebsimEvent('websim_view', { page: '/websim' })
    try {
      const bootstrap = await apiJson('/api/websim/bootstrap')
      state.classes = bootstrap.classes || []
      state.scenarios = bootstrap.scenarios || []
      state.gearSlots = bootstrap.gearSlots || []
      state.instances = bootstrap.instances || []
      state.currentSeason = bootstrap.currentSeason || null
      state.dataStatus = bootstrap.dataStatus || ((bootstrap.currentSeason && bootstrap.currentSeason.dataStatus) || 'blocked')
      applyInitialSelection(bootstrap.defaultSelection || {})
      state.scenarioKey = (state.scenarios[0] && state.scenarios[0].key) || state.scenarioKey
      const syncStatus = $('syncStatus')
      const simcVersion = $('simcVersion')
      if (syncStatus) {
        const sync = bootstrap.syncState || {}
        const hasSimcCache = sync.simc && Number(sync.simc.talents || 0) > 0
        syncStatus.textContent = sync.ok ? '缓存已同步' : (hasSimcCache ? 'SimC 缓存就绪' : '等待官方数据')
      }
      if (simcVersion) simcVersion.textContent = (bootstrap.simcraftVersion && (bootstrap.simcraftVersion.localTag || bootstrap.simcraftVersion.version || bootstrap.simcraftVersion.binary)) || 'SimC'
      renderGateNotice()
      renderSelectors()
      await Promise.all([loadTalents(), loadGear(), loadLoot()])
      renderGateNotice()
      renderProfilePreview()
    } catch (error) {
      showError(error)
    }
  }

  const publicApi = {
    normalizeGearItem,
    filterLootRows,
    buildProfilePayload,
    addGearItem
  }

  if (typeof module !== 'undefined') module.exports = publicApi
  root.WebSimApp = publicApi
  init()
})(typeof window !== 'undefined' ? window : globalThis)
