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
    heroKey: '',
    scenarioKey: 'single',
    talents: [],
    treeSections: [],
    talentStatus: 'fallback',
    talentRanks: {},
    baseTalentRanks: {},
    starterTalentRanks: {},
    talentAnnotations: {},
    showTalentNames: false,
    annotateMode: false,
    talentHelpOpen: false,
    talentSearchTerm: '',
    talentSearchFocusId: '',
    talentSearchIndex: 0,
    talentZoom: 1,
    talentHistoryPast: [],
    talentHistoryFuture: [],
    talentHistoryLimit: 80,
    isRestoringTalentHistory: false,
    footerMenuPanel: '',
    footerImportDraft: '',
    pvpSelections: {},
    activePvpSlot: -1,
    recentTalentId: '',
    recentTalentTone: '',
    recentTalentTimer: 0,
    blockedTalentId: '',
    blockedTalentTimer: 0,
    activeChoiceNodeId: '',
    talentActionTimer: 0,
    talentActionButtonTimer: 0,
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

  const selectorConfigs = {
    class: { selectId: 'classSelect', previewId: 'classSelectPreview', menuId: 'classSelectorMenu' },
    spec: { selectId: 'specSelect', previewId: 'specSelectPreview', menuId: 'specSelectorMenu' },
    hero: { selectId: 'heroSelect', previewId: 'heroSelectPreview', menuId: 'heroSelectorMenu' },
    scenario: { selectId: 'scenarioSelect', previewId: 'scenarioSelectPreview', menuId: 'scenarioSelectorMenu' }
  }

  const talentZoomSteps = [0.85, 1, 1.15]

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
    state.heroKey = selection.heroKey || state.heroKey
    ensureHeroSelection()
    const preferredScenario = state.scenarios.find((item) => item.key === selection.scenarioKey)
    if (preferredScenario) state.scenarioKey = preferredScenario.key
  }

  function selectedSpecLabel() {
    const klass = classByKey(state.classKey)
    const spec = (klass.specs || []).find((item) => item.key === state.specKey)
    return `${klass.label || state.classKey} ${spec ? spec.label : state.specKey}`
  }

  function talentPageTitle() {
    const classMeta = currentClassMeta()
    const specMeta = currentSpecMeta()
    const spec = specMeta.label || specMeta.labelEn || state.specKey || '专精'
    const klass = classMeta.label || classMeta.labelEn || state.classKey || '职业'
    return `${spec}${klass}至暗之夜天赋模拟器`
  }

  function talentDocumentTitle() {
    return `${talentPageTitle()} - SimC 构筑工坊`
  }

  function syncTalentDocumentTitle() {
    if (root.document) root.document.title = talentDocumentTitle()
  }

  function talentPageEyebrow() {
    const specMeta = currentSpecMeta()
    const heroMeta = currentHeroMeta()
    const spec = specMeta.label || specMeta.labelEn || state.specKey || '专精'
    const hero = heroMeta.label || state.heroKey || '英雄天赋'
    return `${spec} · ${hero}`
  }

  function currentClassMeta() {
    return classByKey(state.classKey) || {}
  }

  function currentSpecMeta() {
    const klass = currentClassMeta()
    return (klass.specs || []).find((item) => item.key === state.specKey) || {}
  }

  function currentHeroTrees() {
    const specHeroes = currentSpecMeta().heroTrees
    return (Array.isArray(specHeroes) && specHeroes.length ? specHeroes : currentClassMeta().heroTrees) || []
  }

  function currentHeroMeta() {
    const heroes = currentHeroTrees()
    return heroes.find((item) => item.key === state.heroKey) || heroes[0] || {}
  }

  function currentScenarioMeta() {
    return state.scenarios.find((item) => item.key === state.scenarioKey) || state.scenarios[0] || {}
  }

  function ensureHeroSelection() {
    const heroes = currentHeroTrees()
    if (!heroes.length) {
      state.heroKey = ''
      return
    }
    if (!heroes.some((item) => item.key === state.heroKey)) {
      state.heroKey = heroes[0].key
    }
  }

  function currentAccent() {
    return currentClassMeta().color || '#f1b94c'
  }

  function defaultTreeSections() {
    const klass = currentClassMeta()
    const spec = currentSpecMeta()
    const hero = currentHeroMeta().label || '英雄天赋'
    return [
      { key: 'class', title: klass.label || '职业', titleEn: klass.labelEn || 'Class', pointCap: 34, reqLevel: 10, accent: currentAccent() },
      { key: 'spec', title: spec.label || '专精', titleEn: spec.labelEn || 'Spec', pointCap: 34, reqLevel: 11, accent: currentAccent() },
      { key: 'hero', title: hero, titleEn: hero, pointCap: 13, reqLevel: 71, accent: '#58d3ff' }
    ]
  }

  function talentTreeKey(node) {
    return node.treeType || node.treeId || (node.specKey === 'class' ? 'class' : 'spec')
  }

  function maxRankFor(node) {
    return Math.max(1, Number(node.maxRank || node.rank || 1))
  }

  function rankFor(nodeOrId) {
    const id = typeof nodeOrId === 'string' ? nodeOrId : nodeOrId.id
    return Math.max(0, Number(state.talentRanks[id] || 0))
  }

  function setTalentRank(id, rank) {
    const node = state.talents.find((item) => item.id === id)
    if (!node) return 0
    const next = Math.max(0, Math.min(maxRankFor(node), Number(rank || 0)))
    if (next) state.talentRanks[id] = next
    else delete state.talentRanks[id]
    return next
  }

  function adjustTalentRank(id, delta) {
    const node = state.talents.find((item) => item.id === id)
    if (!node) return 0
    if (delta > 0 && !canIncreaseTalent(node)) return rankFor(id)
    if (delta > 0 && node.choiceGroup) {
      state.talents
        .filter((item) => item.id !== id && item.choiceGroup === node.choiceGroup && talentTreeKey(item) === talentTreeKey(node))
        .forEach((item) => delete state.talentRanks[item.id])
    }
    setTalentRank(id, rankFor(id) + delta)
    clearInvalidTalentRanks(id)
    return rankFor(id)
  }

  function markRecentTalent(id, tone = 'add') {
    state.recentTalentId = id || ''
    state.recentTalentTone = id ? (tone === 'remove' ? 'remove' : 'add') : ''
    if (root.clearTimeout && state.recentTalentTimer) root.clearTimeout(state.recentTalentTimer)
    state.recentTalentTimer = 0
    if (state.recentTalentId && root.setTimeout) {
      state.recentTalentTimer = root.setTimeout(() => {
        if (state.recentTalentId === id) {
          const active = root.document && root.document.activeElement
          const restoreFocus = Boolean(active && active.dataset && active.dataset.talentId === id)
          state.recentTalentId = ''
          state.recentTalentTone = ''
          renderTalents()
          if (restoreFocus) restoreTalentNodeFocus(id)
        }
      }, 900)
    }
  }

  function resetTalentRanks() {
    state.talentRanks = { ...state.baseTalentRanks }
    markRecentTalent('')
  }

  function loadStarterTalentRanks() {
    state.talentRanks = { ...state.starterTalentRanks }
    clearInvalidTalentRanks()
    markRecentTalent('')
  }

  function pruneTalentAnnotations() {
    const validIds = new Set((state.talents || []).map((node) => node.id))
    Object.keys(state.talentAnnotations || {}).forEach((id) => {
      if (!validIds.has(id)) delete state.talentAnnotations[id]
    })
  }

  function toggleTalentAnnotation(id) {
    if (!id) return false
    state.talentAnnotations = state.talentAnnotations || {}
    if (state.talentAnnotations[id]) {
      delete state.talentAnnotations[id]
      return false
    }
    state.talentAnnotations[id] = 'marked'
    return true
  }

  function clearTalentAnnotations() {
    state.talentAnnotations = {}
  }

  function cloneRankMap(ranks = state.talentRanks) {
    return Object.keys(ranks || {}).sort().reduce((copy, id) => {
      const rank = Number(ranks[id] || 0)
      if (rank > 0) copy[id] = rank
      return copy
    }, {})
  }

  function cloneAnnotationMap(annotations = state.talentAnnotations) {
    return Object.keys(annotations || {}).sort().reduce((copy, id) => {
      if (annotations[id]) copy[id] = annotations[id]
      return copy
    }, {})
  }

  function clonePvpSelectionMap(selections = state.pvpSelections) {
    return Object.keys(selections || {}).sort().reduce((copy, key) => {
      const values = Array.isArray(selections[key]) ? selections[key].slice(0, 3) : []
      while (values.length < 3) values.push('')
      copy[key] = values
      return copy
    }, {})
  }

  function talentBuildSnapshot() {
    return {
      classKey: state.classKey,
      specKey: state.specKey,
      heroKey: state.heroKey || '',
      talentRanks: cloneRankMap(),
      talentAnnotations: cloneAnnotationMap(),
      pvpSelections: clonePvpSelectionMap()
    }
  }

  function talentBuildSnapshotSignature(snapshot = talentBuildSnapshot()) {
    return JSON.stringify(snapshot)
  }

  function pushTalentHistorySnapshot(snapshot) {
    if (state.isRestoringTalentHistory || !snapshot) return
    const signature = talentBuildSnapshotSignature(snapshot)
    const last = state.talentHistoryPast[state.talentHistoryPast.length - 1]
    if (last && talentBuildSnapshotSignature(last) === signature) return
    state.talentHistoryPast.push(snapshot)
    while (state.talentHistoryPast.length > state.talentHistoryLimit) state.talentHistoryPast.shift()
    state.talentHistoryFuture = []
    updateTalentToolbarState()
  }

  function clearTalentHistory() {
    state.talentHistoryPast = []
    state.talentHistoryFuture = []
    updateTalentToolbarState()
  }

  async function restoreTalentBuildSnapshot(snapshot) {
    if (!snapshot) return false
    state.isRestoringTalentHistory = true
    try {
      const classChanged = state.classKey !== snapshot.classKey || state.specKey !== snapshot.specKey
      const heroChanged = state.heroKey !== snapshot.heroKey
      state.classKey = snapshot.classKey || state.classKey
      state.specKey = snapshot.specKey || state.specKey
      state.heroKey = snapshot.heroKey || ''
      ensureHeroSelection()
      renderSelectors()
      if (classChanged) {
        await Promise.all([loadTalents(), loadGear()])
      } else if (heroChanged) {
        await loadTalents()
      }
      state.heroKey = snapshot.heroKey || state.heroKey
      ensureHeroSelection()
      state.talentRanks = cloneRankMap(snapshot.talentRanks)
      state.talentAnnotations = cloneAnnotationMap(snapshot.talentAnnotations)
      state.pvpSelections = clonePvpSelectionMap(snapshot.pvpSelections)
      clearInvalidTalentRanks()
      renderSelectors()
      renderTalents()
      renderProfilePreview()
      syncLiveTalentRoute()
      return true
    } finally {
      state.isRestoringTalentHistory = false
      updateTalentToolbarState()
    }
  }

  async function undoTalentHistory() {
    const snapshot = state.talentHistoryPast.pop()
    if (!snapshot) {
      flashTalentAction('', '没有可撤销的操作', 'error')
      updateTalentToolbarState()
      return false
    }
    state.talentHistoryFuture.push(talentBuildSnapshot())
    await restoreTalentBuildSnapshot(snapshot)
    flashTalentAction('', '已撤销')
    return true
  }

  async function redoTalentHistory() {
    const snapshot = state.talentHistoryFuture.pop()
    if (!snapshot) {
      flashTalentAction('', '没有可重做的操作', 'error')
      updateTalentToolbarState()
      return false
    }
    state.talentHistoryPast.push(talentBuildSnapshot())
    await restoreTalentBuildSnapshot(snapshot)
    flashTalentAction('', '已重做')
    return true
  }

  function isEditableShortcutTarget(target) {
    if (!target) return false
    const tag = String(target.tagName || '').toLowerCase()
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
    if (target.isContentEditable) return true
    return Boolean(target.closest && target.closest('[contenteditable="true"], [contenteditable="plaintext-only"]'))
  }

  function handleTalentHistoryShortcut(event) {
    const key = String(event.key || '').toLowerCase()
    const modifier = event.ctrlKey || event.metaKey
    if (!modifier || event.altKey) return false
    if (isEditableShortcutTarget(event.target)) return false
    if (key === 'z' && event.shiftKey) {
      event.preventDefault()
      redoTalentHistory().catch(showError)
      return true
    }
    if (key === 'z') {
      event.preventDefault()
      undoTalentHistory().catch(showError)
      return true
    }
    if (key === 'y') {
      event.preventDefault()
      redoTalentHistory().catch(showError)
      return true
    }
    return false
  }

  function setTalentHelpOpen(open) {
    state.talentHelpOpen = Boolean(open)
    updateTalentToolbarState()
  }

  function updateTalentToolbarState() {
    const tree = $('talentTree')
    if (tree) {
      tree.classList.toggle('show-names', state.showTalentNames)
      tree.classList.toggle('annotate-mode', state.annotateMode)
    }
    const showNamesButton = $('showTalentNamesButton')
    if (showNamesButton) {
      showNamesButton.classList.toggle('active', state.showTalentNames)
      showNamesButton.setAttribute('aria-pressed', String(Boolean(state.showTalentNames)))
      showNamesButton.textContent = state.showTalentNames ? '隐藏名称' : '显示名称'
    }
    const annotateButton = $('annotateTalentsButton')
    if (annotateButton) {
      annotateButton.classList.toggle('active', state.annotateMode)
      annotateButton.setAttribute('aria-pressed', String(Boolean(state.annotateMode)))
      annotateButton.textContent = state.annotateMode ? '退出标记' : '标记模式'
    }
    const helpButton = $('talentHelpButton')
    const helpPanel = $('talentHelpPanel')
    if (helpButton) helpButton.setAttribute('aria-expanded', String(Boolean(state.talentHelpOpen)))
    if (helpPanel) {
      helpPanel.classList.toggle('visible', state.talentHelpOpen)
      helpPanel.setAttribute('aria-hidden', String(!state.talentHelpOpen))
    }
  }

  function talentPoints(treeKey) {
    return state.talents
      .filter((node) => talentTreeKey(node) === treeKey)
      .reduce((total, node) => total + rankFor(node), 0)
  }

  function parentNodesFor(node) {
    const byId = new Map(state.talents.map((item) => [item.id, item]))
    return (node.parentIds || []).map((id) => byId.get(id)).filter(Boolean)
  }

  function parentsSatisfied(node) {
    const parents = parentNodesFor(node)
    return !parents.length || parents.some((parent) => rankFor(parent) > 0)
  }

  function pointRequirementFor(node) {
    return Math.max(0, Number(node.pointRequirement || 0))
  }

  function pointsAvailableForRequirement(node) {
    return Math.max(0, talentPoints(talentTreeKey(node)) - rankFor(node))
  }

  function pointRequirementSatisfied(node) {
    const requirement = pointRequirementFor(node)
    return requirement <= 0 || pointsAvailableForRequirement(node) >= requirement
  }

  function missingParentNodesFor(node) {
    return parentNodesFor(node).filter((parent) => rankFor(parent) <= 0)
  }

  function talentDisabledReason(node) {
    if (!node) return ''
    const rank = rankFor(node)
    const maxRank = maxRankFor(node)
    if (rank >= maxRank) return ''
    const missingParents = missingParentNodesFor(node)
    if (missingParents.length) {
      return `需要先点亮 ${missingParents.map((parent) => parent.name).join(' 或 ')}`
    }
    if (!pointRequirementSatisfied(node)) {
      const section = treeSectionForNode(node)
      const requirement = pointRequirementFor(node)
      const available = pointsAvailableForRequirement(node)
      return `需要先在 ${section.title || section.titleEn || talentTreeKey(node)} 投入 ${requirement} 点（当前计入 ${available} 点）`
    }
    if (!canIncreaseTalent(node) && pointCapReached(node)) {
      const pointCap = pointCapFor(node)
      return `本树最多投入 ${pointCap} 点`
    }
    return ''
  }

  function missingRequiredTalentIdsFor(node) {
    return new Set(missingParentNodesFor(node).map((parent) => parent.id))
  }

  function activeBlockedTalentNode() {
    return state.blockedTalentId ? state.talents.find((node) => node.id === state.blockedTalentId) || null : null
  }

  function talentPointWord(count) {
    return '点'
  }

  function talentTreeTitleForNode(node) {
    const section = treeSectionForNode(node)
    return section.title || section.titleEn || talentTreeKey(node)
  }

  function talentStepStateLabel(value) {
    return {
      next: '下一步',
      required: '前置',
      gate: '门槛',
      locked: '锁定',
      cap: '上限'
    }[value] || '锁定'
  }

  function talentStepShortTitle(title) {
    return String(title || '')
      .replace(/^点亮\s+/, '')
      .replace(/^继续提升\s+/, '')
      .replace(/^解锁\s+/, '')
      .replace(/^推进\s+/, '')
      .replace(/^在\s+(.+?)\s+再投入\s+\d+\s+点$/, '$1')
  }

  function sortTalentRouteNodes(nodes) {
    return (nodes || []).slice().sort((a, b) =>
      Number(a.row || 0) - Number(b.row || 0)
      || Number(a.col || 0) - Number(b.col || 0)
      || String(a.name || '').localeCompare(String(b.name || ''))
    )
  }

  function compactTalentUnlockSteps(steps, limit = 4) {
    const seen = new Set()
    const compacted = []
    ;(steps || []).forEach((step) => {
      const key = step.key || `${step.state}:${step.title}`
      if (!step.title || seen.has(key)) return
      seen.add(key)
      compacted.push(step)
    })
    return compacted.slice(0, limit)
  }

  function talentUnlockProgressFor(node, steps = talentUnlockStepsFor(node)) {
    if (!node) return null
    const context = talentBlockingContextFor(node)
    const byId = new Map(state.talents.map((item) => [item.id, item]))
    const hasMissingParents = missingParentNodesFor(node).length > 0
    const routeNodes = hasMissingParents
      ? sortTalentRouteNodes(Array.from(context.nodeIds).map((id) => byId.get(id)).filter(Boolean))
      : []
    const routeRankTotal = routeNodes.reduce((total, item) => total + maxRankFor(item), 0)
    const routeRankReady = routeNodes.reduce((total, item) => total + Math.min(rankFor(item), maxRankFor(item)), 0)
    const routeRanksLeft = Math.max(0, routeRankTotal - routeRankReady)
    const addableCount = (steps || []).filter((step) => step.canAdd && step.targetId).length
    const items = []
    if (routeRankTotal) {
      items.push({
        detail: routeRanksLeft ? `还差 ${routeRanksLeft} ${talentPointWord(routeRanksLeft)}` : '已就绪',
        label: '前置',
        tone: routeRanksLeft ? 'route' : 'done',
        value: `${routeRankReady}/${routeRankTotal}`
      })
    }
    if (!pointRequirementSatisfied(node)) {
      const requirement = pointRequirementFor(node)
      const available = pointsAvailableForRequirement(node)
      const remaining = Math.max(0, requirement - available)
      items.push({
        detail: remaining ? `还差 ${remaining} ${talentPointWord(remaining)}` : '已就绪',
        label: '门槛',
        tone: remaining ? 'gate' : 'done',
        value: `${Math.min(available, requirement)}/${requirement}`
      })
    }
    if (addableCount) {
      items.push({
        detail: '可立即加点',
        label: '可加点',
        tone: 'next',
        value: String(addableCount)
      })
    }
    if (!items.length && rankFor(node) < maxRankFor(node)) {
      items.push({
        detail: '目标可点',
        label: '前置',
        tone: 'done',
        value: '就绪'
      })
    }
    return { addableCount, items, routeRankReady, routeRankTotal, routeRanksLeft }
  }

  function talentUnlockProgressMarkup(progress, className) {
    if (!progress || !progress.items || !progress.items.length) return ''
    return `<div class="${escapeHtml(className)}" data-unlock-progress aria-label="解锁进度">
      ${progress.items.map((item) => `<span class="${escapeHtml(`${className}-item`)}" data-progress-tone="${escapeHtml(item.tone || 'route')}">
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.value)}</span>
        <em>${escapeHtml(item.detail)}</em>
      </span>`).join('')}
    </div>`
  }

  function talentRouteStepForNode(node) {
    const rank = rankFor(node)
    const maxRank = maxRankFor(node)
    return {
      canAdd: true,
      detail: `${talentTreeTitleForNode(node)} ${rank}/${maxRank}`,
      key: `next:${node.id}`,
      state: 'next',
      targetId: node.id,
      title: `${rank > 0 ? '继续提升' : '点亮'} ${node.name}`
    }
  }

  function talentUnlockActionPriority(node) {
    const parents = parentNodesFor(node)
    if (parents.some((parent) => rankFor(parent) > 0)) return 0
    return parents.length ? 1 : 2
  }

  function talentUnlockStepsFor(node, limit = 4) {
    if (!node || rankFor(node) >= maxRankFor(node)) return []
    const steps = []
    const missingParents = missingParentNodesFor(node)
    if (missingParents.length) {
      sortTalentRouteNodes(missingParents).slice(0, 2).forEach((parent) => {
        if (canIncreaseTalent(parent)) {
          steps.push(talentRouteStepForNode(parent))
        } else {
          const parentReason = talentDisabledReason(parent) || '前置节点仍未解锁'
          steps.push({
            detail: parentReason,
            key: `required:${parent.id}`,
            state: 'required',
            targetId: parent.id,
            title: `先解锁 ${parent.name}`
          })
        }
      })
    }

    if (!pointRequirementSatisfied(node)) {
      const section = treeSectionForNode(node)
      const requirement = pointRequirementFor(node)
      const available = pointsAvailableForRequirement(node)
      const remaining = Math.max(0, requirement - available)
      const title = section.title || section.titleEn || talentTreeKey(node)
      const candidates = talentGateCandidateNodesFor(node, Math.max(1, Math.min(limit, remaining || 1)))
      candidates.forEach((candidate) => {
        const step = talentRouteStepForNode(candidate)
        step.key = `gate:${candidate.id}`
        step.state = 'gate'
        step.detail = `补足 ${title} 门槛 ${available}/${requirement}`
        steps.push(step)
      })
      if (!candidates.length) {
        steps.push({
          detail: `门槛 ${available}/${requirement}`,
          key: `gate:${node.id}`,
          state: 'gate',
          targetId: node.id,
          title: `在 ${title} 再投入 ${remaining} ${talentPointWord(remaining)}`
        })
      }
    }

    if (!steps.length && pointCapReached(node)) {
      const pointCap = pointCapFor(node)
      steps.push({
        detail: `${talentTreeTitleForNode(node)} 已达上限`,
        key: `cap:${node.id}`,
        state: 'cap',
        targetId: node.id,
        title: `从本树移除 1 点（${pointCap}/${pointCap}）`
      })
    }

    const reason = talentDisabledReason(node)
    if (!steps.length && reason) {
      steps.push({
        detail: reason,
        key: `reason:${node.id}`,
        state: 'locked',
        targetId: node.id,
        title: '查看锁定条件'
      })
    }
    return compactTalentUnlockSteps(steps, limit)
  }

  function talentBlockedFlashMessage(node) {
    const reason = talentDisabledReason(node)
    const nextStep = talentUnlockStepsFor(node).find((step) => step.state === 'next' || step.state === 'gate')
    return nextStep ? `${reason}；下一步：${nextStep.title}` : reason
  }

  function talentUnlockPrimaryStep(steps) {
    return (steps || []).find((step) => step.canAdd && step.targetId) || null
  }

  function talentUnlockStepsMarkup(steps, className) {
    if (!steps || !steps.length) return ''
    const interactive = className === 'talent-unlock-steps'
    const stepContent = (step) => `
        <span class="${escapeHtml(`${className}-state`)}">${escapeHtml(talentStepStateLabel(step.state))}</span>
        <strong>${escapeHtml(step.title)}</strong>
        <span>${escapeHtml(step.detail || '')}</span>`
    return `<ol class="${escapeHtml(className)}">
      ${steps.map((step) => {
        const addable = interactive && step.canAdd && step.targetId
        return `<li class="${escapeHtml(`${className}-item`)} ${addable ? 'has-action' : ''}" data-step-state="${escapeHtml(step.state || 'locked')}"${step.targetId ? ` data-step-target="${escapeHtml(step.targetId)}"` : ''}>
        ${interactive && step.targetId
          ? `<button type="button" class="${escapeHtml(`${className}-button`)}" data-unlock-step data-target-id="${escapeHtml(step.targetId)}" aria-label="${escapeHtml(`查看 ${step.title}`)}">${stepContent(step)}</button>`
          : stepContent(step)}
        ${addable ? `<button type="button" class="talent-unlock-step-add" data-unlock-step-add data-target-id="${escapeHtml(step.targetId)}" aria-label="${escapeHtml(`给 ${talentStepShortTitle(step.title)} 加 1 点`)}">+</button>` : ''}
      </li>`
      }).join('')}
    </ol>`
  }

  function talentUnlockGuideMarkup(node) {
    if (!node) return ''
    const reason = talentDisabledReason(node)
    const steps = talentUnlockStepsFor(node)
    if (!reason && !steps.length) return ''
    const primaryStep = talentUnlockPrimaryStep(steps)
    const progress = talentUnlockProgressFor(node, steps)
    const actionLabel = primaryStep && String(primaryStep.key || '').startsWith('gate:') ? '推荐加点' : '继续路径'
    const action = primaryStep
      ? `<button type="button" class="talent-unlock-guide-action" data-unlock-step-continue data-target-id="${escapeHtml(primaryStep.targetId)}" aria-label="${escapeHtml(`${actionLabel}：${primaryStep.title}`)}">
          <span>${escapeHtml(actionLabel)}</span>
          <strong>${escapeHtml(talentStepShortTitle(primaryStep.title))}</strong>
        </button>`
      : ''
    return `<div class="talent-unlock-guide" data-unlock-guide aria-live="polite">
      <div class="talent-unlock-guide-copy">
        <span>天赋未解锁</span>
        <strong>解锁 ${escapeHtml(node.name)}</strong>
        <em>${escapeHtml(reason || '按高亮路径继续。')}</em>
      </div>
      ${action}
      ${talentUnlockProgressMarkup(progress, 'talent-unlock-progress')}
      ${talentUnlockStepsMarkup(steps, 'talent-unlock-steps')}
      <button type="button" class="talent-unlock-guide-dismiss" data-unlock-dismiss aria-label="关闭解锁提示">&times;</button>
    </div>`
  }

  function talentTooltipUnlockGuideHtml(node) {
    const steps = talentUnlockStepsFor(node)
    const progress = talentUnlockProgressFor(node, steps)
    if (!steps.length) return ''
    return `<div class="tooltip-unlock-guide">
      <div class="tooltip-unlock-title">下一步</div>
      ${talentUnlockProgressMarkup(progress, 'tooltip-unlock-progress')}
      ${talentUnlockStepsMarkup(steps, 'tooltip-unlock-steps')}
    </div>`
  }

  function setBlockedTalentFeedback(node) {
    const reason = talentDisabledReason(node)
    if (!reason) return false
    state.blockedTalentId = node.id
    setTalentHoverState(node, true)
    flashTalentAction('', talentBlockedFlashMessage(node), 'error')
    scheduleBlockedTalentFeedbackClear(node.id)
    return true
  }

  function scheduleBlockedTalentFeedbackClear(id = state.blockedTalentId) {
    if (root.clearTimeout && state.blockedTalentTimer) root.clearTimeout(state.blockedTalentTimer)
    state.blockedTalentTimer = 0
    if (root.setTimeout) {
      state.blockedTalentTimer = root.setTimeout(() => {
        if (state.blockedTalentId === id) {
          clearBlockedTalentFeedback()
        }
      }, 15000)
    }
  }

  function clearBlockedTalentFeedback(options = {}) {
    const render = typeof options === 'boolean' ? options : options.render !== false
    const restoreFocus = Boolean(options && typeof options === 'object' && options.restoreFocus)
    const blockedId = state.blockedTalentId
    if (!state.blockedTalentId && !state.blockedTalentTimer) return false
    state.blockedTalentId = ''
    if (root.clearTimeout && state.blockedTalentTimer) root.clearTimeout(state.blockedTalentTimer)
    state.blockedTalentTimer = 0
    clearTalentUnlockStepPreview()
    setTalentHoverState(null, false)
    if (render) renderTalents()
    if (restoreFocus && blockedId) restoreTalentNodeFocus(blockedId)
    return true
  }

  function clearResolvedBlockedTalentFeedback() {
    const blockedNode = activeBlockedTalentNode()
    if (!blockedNode) return false
    const resolved = canIncreaseTalent(blockedNode) || rankFor(blockedNode) >= maxRankFor(blockedNode)
    if (!resolved) return false
    return clearBlockedTalentFeedback({ render: false })
  }

  function treeSectionForNode(node) {
    const key = talentTreeKey(node)
    return (state.treeSections || []).find((section) => section.key === key)
      || defaultTreeSections().find((section) => section.key === key)
      || {}
  }

  function orderedTreeSections(sections) {
    const order = { class: 0, hero: 1, spec: 2 }
    return (sections || []).slice().sort((a, b) => {
      const left = order[a.key] == null ? 9 : order[a.key]
      const right = order[b.key] == null ? 9 : order[b.key]
      return left - right
    })
  }

  function treeReqLevelFor(section) {
    const fallback = section && section.key === 'hero' ? 71 : (section && section.key === 'class' ? 10 : 11)
    const value = Number((section && section.reqLevel) || fallback)
    return Number.isFinite(value) && value > 0 ? value : fallback
  }

  function gateRequirementsForNodes(nodes) {
    const gates = new Map()
    ;(nodes || []).forEach((node) => {
      const requirement = pointRequirementFor(node)
      const row = Math.max(1, Number(node.row || 1))
      if (requirement <= 0 || row <= 1) return
      const existing = gates.get(requirement)
      if (!existing || row < existing.row) gates.set(requirement, { requirement, row })
    })
    return Array.from(gates.values()).sort((a, b) => a.row - b.row || a.requirement - b.requirement)
  }

  function treeGateStatus(section, nodes) {
    const spent = talentPoints(section.key)
    const gates = gateRequirementsForNodes(nodes)
    const next = gates.find((gate) => spent < gate.requirement) || null
    const state = next ? 'locked' : (gates.length ? 'unlocked' : 'none')
    const remaining = next ? Math.max(0, next.requirement - spent) : 0
    const label = next
      ? `下一道门槛：${next.requirement} 点`
      : (gates.length ? '全部门槛已开启' : '无门槛')
    const detail = next ? `还差 ${remaining} 点` : (gates.length ? '已开启' : '开放')
    return { detail, gates, label, next, remaining, spent, state }
  }

  function treeHeaderMarkup(section, nodes) {
    const spent = talentPoints(section.key)
    const pointCap = Number(section.pointCap || (nodes && nodes.length) || 0)
    const cap = Number.isFinite(pointCap) && pointCap > 0 ? pointCap : ((nodes && nodes.length) || 0)
    const progress = cap > 0 ? Math.max(0, Math.min(100, (spent / cap) * 100)) : 0
    const progressState = spent >= cap ? 'complete' : (spent > 0 ? 'partial' : 'empty')
    const title = section.title || section.titleEn || section.key
    const gateStatus = treeGateStatus(section, nodes)
    const blockedNode = activeBlockedTalentNode()
    const blockedAttention = Boolean(blockedNode && talentTreeKey(blockedNode) === section.key && !pointRequirementSatisfied(blockedNode))
    const progressLabel = `${title} 已投入 ${spent} 点；${gateStatus.label} ${gateStatus.detail}`
    return `<div class="tree-header tree-header-${escapeHtml(section.key)} ${blockedAttention ? 'tree-header-attention' : ''}" data-next-gate-state="${escapeHtml(gateStatus.state)}" aria-label="${escapeHtml(title)}">
      <div class="tree-header-title">
        <h3>${escapeHtml(title)}</h3>
      </div>
      <div class="tree-header-stats">
        <span>已投入：<strong>${escapeHtml(spent)} / ${escapeHtml(cap)}</strong></span>
        <span>需求等级：<strong>${escapeHtml(treeReqLevelFor(section))}</strong></span>
        <span class="tree-header-next-gate" data-next-gate-state="${escapeHtml(gateStatus.state)}">${escapeHtml(gateStatus.label)} <strong>${escapeHtml(gateStatus.detail)}</strong></span>
      </div>
      <div class="tree-header-progress tree-header-progress-${escapeHtml(progressState)}" role="meter" aria-label="${escapeHtml(progressLabel)}" aria-valuemin="0" aria-valuemax="${escapeHtml(cap)}" aria-valuenow="${escapeHtml(spent)}">
        <span class="tree-header-progress-fill" style="--tree-progress:${progress.toFixed(2)}%;"></span>
      </div>
    </div>`
  }

  function pointCapFor(node) {
    const pointCap = Number(treeSectionForNode(node).pointCap || 0)
    return Number.isFinite(pointCap) && pointCap > 0 ? pointCap : 0
  }

  function pointCapReached(node) {
    const pointCap = pointCapFor(node)
    return pointCap > 0 && talentPoints(talentTreeKey(node)) >= pointCap
  }

  function canIncreaseTalent(node) {
    const pointCap = pointCapFor(node)
    const underCap = pointCap <= 0 || talentPoints(talentTreeKey(node)) < pointCap
    const selectedChoicePeer = node.choiceGroup && rankFor(node) <= 0 ? selectedChoicePeerFor(node) : null
    return parentsSatisfied(node) && pointRequirementSatisfied(node) && rankFor(node) < maxRankFor(node) && (underCap || Boolean(selectedChoicePeer))
  }

  function clearInvalidTalentRanks(preferredId = '') {
    let changed = true
    while (changed) {
      changed = false
      state.talents.forEach((node) => {
        if (rankFor(node) > 0 && (!parentsSatisfied(node) || !pointRequirementSatisfied(node))) {
          delete state.talentRanks[node.id]
          changed = true
        }
      })
      const selectedChoiceGroups = new Map()
      state.talents.forEach((node) => {
        if (!node.choiceGroup || rankFor(node) <= 0) return
        const key = `${talentTreeKey(node)}:${node.choiceGroup}`
        const existingId = selectedChoiceGroups.get(key)
        if (!existingId) {
          selectedChoiceGroups.set(key, node.id)
          return
        }
        const dropId = preferredId && node.id === preferredId ? existingId : node.id
        const keepId = dropId === existingId ? node.id : existingId
        delete state.talentRanks[dropId]
        selectedChoiceGroups.set(key, keepId)
        changed = true
      })
    }
  }

  function selectedTalentEntries() {
    return state.talents
      .filter((node) => rankFor(node) > 0)
      .map((node) => ({ id: node.id, rank: rankFor(node), tree: talentTreeKey(node), name: node.name }))
  }

  function talentRankSignature(ranks = {}) {
    return Object.keys(ranks)
      .filter((id) => Number(ranks[id] || 0) > 0)
      .sort()
      .map((id) => `${id}:${Number(ranks[id] || 0)}`)
      .join(',')
  }

  function pvpSelectionSignature(selections = pvpSelectionsForCurrentSpec()) {
    return (selections || []).slice(0, 3).map((id) => String(id || '')).join('|')
  }

  function hasLiveTalentBuild() {
    return talentRankSignature(state.talentRanks) !== talentRankSignature(state.baseTalentRanks) || pvpSelectionSignature() !== '||'
  }

  function encodePvpBuildSelections(selections = pvpSelectionsForCurrentSpec()) {
    const normalized = (selections || []).slice(0, 3)
    while (normalized.length < 3) normalized.push('')
    return normalized.map((id) => encodeURIComponent(String(id || ''))).join(',')
  }

  function decodePvpBuildSelections(value = '') {
    const decoded = String(value || '').split(',').slice(0, 3).map((id) => {
      try {
        return decodeURIComponent(id)
      } catch (error) {
        return id
      }
    })
    while (decoded.length < 3) decoded.push('')
    return decoded
  }

  function groupTalentsByTree(nodes) {
    return (nodes || []).reduce((groups, node) => {
      const key = talentTreeKey(node)
      if (!groups[key]) groups[key] = []
      groups[key].push(node)
      return groups
    }, {})
  }

  function talentSelectionFromBuildCode(value) {
    const text = String(value || '').trim()
    if (!text.startsWith('websim:')) return {}
    const parts = text.split(':')
    return {
      classKey: parts[1] || '',
      specKey: parts[2] || '',
      heroKey: parts[3] || '',
      buildCode: text
    }
  }

  function talentSelectionFromLocation() {
    if (!root.location || typeof root.URLSearchParams !== 'function') return {}
    const params = new root.URLSearchParams(root.location.search || '')
    const buildCode = params.get('build') || params.get('talents') || ''
    const buildSelection = talentSelectionFromBuildCode(buildCode)
    const selection = { ...buildSelection }
    const classKey = params.get('class') || params.get('classKey') || buildSelection.classKey || ''
    const specKey = params.get('spec') || params.get('specKey') || buildSelection.specKey || ''
    const heroKey = params.get('hero') || params.get('heroKey') || buildSelection.heroKey || ''
    const scenarioKey = params.get('scenario') || params.get('scenarioKey') || ''
    if (classKey) selection.classKey = classKey
    if (specKey) selection.specKey = specKey
    if (heroKey) selection.heroKey = heroKey
    if (scenarioKey) selection.scenarioKey = scenarioKey
    if (buildCode) selection.buildCode = buildCode
    return selection
  }

  function buildTalentRouteUrl(includeOrigin = true, options = {}) {
    if (!root.location || typeof root.URL !== 'function') return ''
    const url = new root.URL(root.location.href)
    url.searchParams.delete('build')
    url.searchParams.delete('talents')
    url.searchParams.set('class', state.classKey)
    url.searchParams.set('spec', state.specKey)
    if (state.heroKey) url.searchParams.set('hero', state.heroKey)
    else url.searchParams.delete('hero')
    if (state.scenarioKey) url.searchParams.set('scenario', state.scenarioKey)
    if (options.includeBuild && hasLiveTalentBuild()) url.searchParams.set('build', buildTalentExportCode())
    return includeOrigin ? url.toString() : `${url.pathname}${url.search}${url.hash || ''}`
  }

  function buildTalentShareUrl() {
    if (!root.location || typeof root.URL !== 'function') return buildTalentExportCode()
    const url = new root.URL(buildTalentRouteUrl(true))
    url.searchParams.set('build', buildTalentExportCode())
    return url.toString()
  }

  function talentRouteState() {
    return {
      websimSelection: {
        classKey: state.classKey,
        specKey: state.specKey,
        heroKey: state.heroKey,
        scenarioKey: state.scenarioKey
      }
    }
  }

  function syncTalentRoute(options = {}) {
    if (!root.history || !root.location) return
    const method = options.replace ? 'replaceState' : 'pushState'
    if (typeof root.history[method] !== 'function') return
    const next = buildTalentRouteUrl(false, { includeBuild: Boolean(options.includeBuild) })
    const current = `${root.location.pathname}${root.location.search}${root.location.hash || ''}`
    if (next && next !== current) {
      root.history[method](talentRouteState(), '', next)
    } else if (options.replace && typeof root.history.replaceState === 'function') {
      root.history.replaceState(talentRouteState(), '', current)
    }
  }

  function syncLiveTalentRoute() {
    syncTalentRoute({ replace: true, includeBuild: true })
  }

  function buildTalentExportCode() {
    const entries = selectedTalentEntries()
      .map((item) => `${item.id}:${item.rank}`)
      .join(',')
    const pvp = pvpSelectionSignature() !== '||' ? `;pvp=${encodePvpBuildSelections()}` : ''
    return `websim:${state.classKey}:${state.specKey}:${state.heroKey || ''}:${entries}${pvp}`
  }

  function applyTalentExportCode(value) {
    const text = String(value || '').trim()
    if (!text.startsWith('websim:')) return false
    const ranks = {}
    const parts = text.split(':')
    const heroCandidate = parts[3] || ''
    const hasHeroSegment = currentHeroTrees().some((item) => item.key === heroCandidate)
    if (hasHeroSegment) state.heroKey = heroCandidate
    ensureHeroSelection()
    const payload = parts.slice(hasHeroSegment ? 4 : 3).join(':')
    const [rankPayload, ...metadata] = payload.split(';')
    rankPayload.split(',').forEach((entry) => {
      const [id, rank] = entry.split(':')
      const node = state.talents.find((item) => item.id === id)
      if (node) ranks[id] = Math.max(1, Math.min(maxRankFor(node), Number(rank || 1)))
    })
    const pvpPayload = metadata.find((entry) => entry.startsWith('pvp='))
    setPvpSelectionsForCurrentSpec(pvpPayload ? decodePvpBuildSelections(pvpPayload.slice(4)) : ['', '', ''])
    state.talentRanks = ranks
    clearInvalidTalentRanks()
    return true
  }

  function talentGridMetrics(nodes) {
    return {
      cols: Math.max(4, ...nodes.map((node) => Number(node.col || 1))),
      rows: Math.max(4, ...nodes.map((node) => Number(node.row || 1)))
    }
  }

  function talentTreeImage(treeKey) {
    if (treeKey === 'class') return currentClassMeta().iconUrl || ''
    return currentSpecMeta().iconUrl || currentClassMeta().iconUrl || ''
  }

  function heroTreeIconUrl() {
    const heroNode = state.talents.find((node) => talentTreeKey(node) === 'hero' && node.iconUrl)
    return (heroNode && heroNode.iconUrl) || currentSpecMeta().iconUrl || currentClassMeta().iconUrl || ''
  }

  function talentChromeIconButton(kind, value, label, iconUrl, selected) {
    const icon = iconUrl
      ? `<img src="${escapeHtml(iconUrl)}" alt="">`
      : `<span>${escapeHtml(selectorInitial(label || value))}</span>`
    return `<button class="talent-chrome-tab ${selected ? 'active' : ''} talent-chrome-tab-${escapeHtml(kind)}" type="button" data-talent-nav-kind="${escapeHtml(kind)}" data-value="${escapeHtml(value)}" aria-pressed="${selected ? 'true' : 'false'}" aria-label="${escapeHtml(label || value)}">${icon}</button>`
  }

  function talentChromeIconStripMarkup() {
    const classButtons = (state.classes || []).map((item) =>
      talentChromeIconButton('class', item.key, item.label || item.labelEn || item.key, item.iconUrl, item.key === state.classKey)
    )
    const classMeta = currentClassMeta()
    const specButtons = (classMeta.specs || []).map((item) =>
      talentChromeIconButton('spec', item.key, item.label || item.labelEn || item.key, item.iconUrl || classMeta.iconUrl, item.key === state.specKey)
    )
    const heroIcon = heroTreeIconUrl()
    const heroButtons = currentHeroTrees().map((item) =>
      talentChromeIconButton('hero', item.key, item.label || item.key, item.iconUrl || heroIcon, item.key === state.heroKey)
    )
    return `<div class="talent-icon-strip" aria-label="天赋导航">
      <div class="talent-icon-strip-frame">
        ${classButtons.join('')}
        <span class="talent-icon-divider" aria-hidden="true"></span>
        ${specButtons.join('')}
        <span class="talent-icon-divider" aria-hidden="true"></span>
        ${heroButtons.join('')}
      </div>
    </div>`
  }

  function heroFeatureMarkup(section) {
    if (!section || section.key !== 'hero') return ''
    const heroMeta = currentHeroMeta()
    const iconUrl = heroTreeIconUrl()
    const icon = iconUrl
      ? `<img src="${escapeHtml(iconUrl)}" alt="">`
      : `<span>${escapeHtml(selectorInitial(heroMeta.label || section.title || state.heroKey))}</span>`
    return `<div class="talent-hero-feature" aria-hidden="true">
      <strong>${escapeHtml(heroMeta.label || section.title || state.heroKey || '英雄天赋')}</strong>
      <span class="talent-hero-emblem">${icon}</span>
    </div>`
  }

  function talentChromeTabButtons(button) {
    const frame = button && button.closest ? button.closest('.talent-icon-strip-frame') : null
    const scope = frame || (root.document && root.document.querySelector('.talent-icon-strip-frame'))
    return scope ? Array.from(scope.querySelectorAll('.talent-chrome-tab')) : []
  }

  function focusTalentChromeTab(button, direction) {
    const buttons = talentChromeTabButtons(button)
    if (!buttons.length) return false
    const currentIndex = Math.max(0, buttons.indexOf(button))
    const nextIndex = direction === 'home' ? 0
      : direction === 'end' ? buttons.length - 1
        : (currentIndex + (direction === 'next' ? 1 : -1) + buttons.length) % buttons.length
    const target = buttons[nextIndex]
    if (target && target.focus) target.focus()
    return Boolean(target)
  }

  function selectTalentChromeTab(button) {
    const kind = button && (button.dataset.talentNavKind || '')
    const value = button && (button.dataset.value || '')
    if (!kind || !value || value === selectedValueForSelector(kind)) return false
    selectSelectorOption(kind, value)
    return true
  }

  function handleTalentChromeTabKeydown(event, button) {
    const key = event.key
    const direction = key === 'ArrowRight' || key === 'ArrowDown' ? 'next'
      : key === 'ArrowLeft' || key === 'ArrowUp' ? 'prev'
        : key === 'Home' ? 'home'
          : key === 'End' ? 'end'
            : ''
    if (direction) {
      event.preventDefault()
      focusTalentChromeTab(button, direction)
      return
    }
    if (key === 'Enter' || key === ' ') {
      event.preventDefault()
      event.stopPropagation()
      selectTalentChromeTab(button)
    }
  }

  function selectedTalentPoints() {
    return (state.treeSections && state.treeSections.length ? state.treeSections : defaultTreeSections())
      .reduce((total, section) => total + talentPoints(section.key), 0)
  }

  function normalizeTalentZoom(value) {
    const numeric = Number(value || 1)
    return talentZoomSteps.reduce((best, step) =>
      Math.abs(step - numeric) < Math.abs(best - numeric) ? step : best
    , 1)
  }

  function talentZoomPercent() {
    return `${Math.round(normalizeTalentZoom(state.talentZoom) * 100)}%`
  }

  function applyTalentZoomToDom() {
    const zoom = normalizeTalentZoom(state.talentZoom)
    const frame = root.document && root.document.querySelector('.talent-calculator-frame')
    if (frame) frame.style.setProperty('--talent-zoom', zoom.toFixed(2))
    const label = root.document && root.document.querySelector('[data-talent-zoom-label]')
    if (label) label.textContent = talentZoomPercent()
    if (root.document) {
      root.document.querySelectorAll('[data-talent-zoom]').forEach((button) => {
        const action = button.dataset.talentZoom || ''
        const disabled = (action === 'out' && zoom <= talentZoomSteps[0])
          || (action === 'in' && zoom >= talentZoomSteps[talentZoomSteps.length - 1])
          || (action === 'reset' && zoom === 1)
        button.disabled = disabled
        button.setAttribute('aria-disabled', String(disabled))
      })
    }
  }

  function setTalentZoom(value) {
    state.talentZoom = normalizeTalentZoom(value)
    applyTalentZoomToDom()
  }

  function shiftTalentZoom(direction) {
    const zoom = normalizeTalentZoom(state.talentZoom)
    const index = talentZoomSteps.indexOf(zoom)
    const nextIndex = Math.max(0, Math.min(talentZoomSteps.length - 1, index + direction))
    setTalentZoom(talentZoomSteps[nextIndex])
  }

  function talentViewControlsMarkup() {
    return `<div class="talent-view-controls" aria-label="天赋视图控制">
      <button type="button" class="talent-view-button" data-talent-zoom="out" aria-label="缩小">-</button>
      <output class="talent-view-label" data-talent-zoom-label>${escapeHtml(talentZoomPercent())}</output>
      <button type="button" class="talent-view-button" data-talent-zoom="reset" aria-label="重置缩放">1:1</button>
      <button type="button" class="talent-view-button" data-talent-zoom="in" aria-label="放大">+</button>
    </div>`
  }

  function normalizedTalentSearchTerm() {
    return String(state.talentSearchTerm || '').trim().toLowerCase()
  }

  function talentSearchText(node) {
    return [
      node.name,
      node.description,
      treeSectionForNode(node).title,
      treeSectionForNode(node).titleEn,
      node.choiceGroup
    ].filter(Boolean).join(' ').toLowerCase()
  }

  function talentMatchesSearch(node) {
    const term = normalizedTalentSearchTerm()
    return !term || talentSearchText(node).includes(term)
  }

  function talentSearchMatches() {
    const term = normalizedTalentSearchTerm()
    if (!term) return []
    return state.talents
      .filter((node) => talentSearchText(node).includes(term))
      .sort((a, b) => {
        const order = { class: 0, hero: 1, spec: 2 }
        const left = order[talentTreeKey(a)] == null ? 9 : order[talentTreeKey(a)]
        const right = order[talentTreeKey(b)] == null ? 9 : order[talentTreeKey(b)]
        return left - right
          || Number(a.row || 0) - Number(b.row || 0)
          || Number(a.col || 0) - Number(b.col || 0)
      })
  }

  function normalizeTalentSearchIndex(matches = talentSearchMatches()) {
    if (!matches.length) {
      state.talentSearchIndex = 0
      return 0
    }
    const index = Number(state.talentSearchIndex || 0)
    state.talentSearchIndex = Math.max(0, Math.min(matches.length - 1, index))
    return state.talentSearchIndex
  }

  function talentSearchControlsMarkup() {
    const matches = talentSearchMatches()
    const index = normalizeTalentSearchIndex(matches)
    const active = Boolean(normalizedTalentSearchTerm())
    const disabled = !matches.length
    const label = active ? `${matches.length ? index + 1 : 0}/${matches.length}` : ''
    return `<span class="talent-search-nav ${active ? 'active' : ''}" data-talent-search-nav>
      <button type="button" class="talent-search-step" data-talent-search-step="-1" aria-label="上一个搜索结果" ${disabled ? 'disabled aria-disabled="true"' : ''}>&lt;</button>
      <span class="talent-search-count" data-talent-search-count>${escapeHtml(label)}</span>
      <button type="button" class="talent-search-step" data-talent-search-step="1" aria-label="下一个搜索结果" ${disabled ? 'disabled aria-disabled="true"' : ''}>&gt;</button>
    </span>`
  }

  function focusTalentNodeById(id) {
    if (!root.document || !id) return
    const node = Array.from(root.document.querySelectorAll('.talent-node'))
      .find((item) => item.dataset.talentId === id)
    if (!node) return
    if (node.scrollIntoView) node.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' })
    if (node.focus) node.focus({ preventScroll: true })
  }

  function markTalentUnlockStepFocus(id) {
    if (!root.document || !id) return false
    root.document.querySelectorAll('.talent-node.unlock-step-focus').forEach((item) => item.classList.remove('unlock-step-focus'))
    const button = Array.from(root.document.querySelectorAll('.talent-node'))
      .find((item) => item.dataset.talentId === id)
    if (!button) return false
    button.classList.add('unlock-step-focus')
    if (root.clearTimeout && state.unlockStepFocusTimer) root.clearTimeout(state.unlockStepFocusTimer)
    state.unlockStepFocusTimer = 0
    if (root.setTimeout) {
      state.unlockStepFocusTimer = root.setTimeout(() => {
        button.classList.remove('unlock-step-focus')
        state.unlockStepFocusTimer = 0
      }, 1600)
    }
    return true
  }

  function clearTalentUnlockStepPreview(id = '') {
    if (!root.document) return false
    root.document.querySelectorAll('.talent-node.unlock-step-preview').forEach((item) => {
      if (!id || item.dataset.talentId === id) item.classList.remove('unlock-step-preview')
    })
    return true
  }

  function setTalentUnlockStepPreview(id, active = true) {
    if (!root.document || !id) return false
    clearTalentUnlockStepPreview()
    if (!active) return true
    const button = Array.from(root.document.querySelectorAll('.talent-node'))
      .find((item) => item.dataset.talentId === id)
    if (!button) return false
    button.classList.add('unlock-step-preview')
    return true
  }

  function bindTalentUnlockStepPreview(button) {
    if (!button || !button.dataset) return
    const targetId = button.dataset.targetId || ''
    if (!targetId) return
    const show = () => setTalentUnlockStepPreview(targetId, true)
    const hide = () => clearTalentUnlockStepPreview(targetId)
    button.addEventListener('pointerenter', show)
    button.addEventListener('pointerleave', hide)
    button.addEventListener('mouseenter', show)
    button.addEventListener('mouseleave', hide)
    button.addEventListener('focus', show)
    button.addEventListener('blur', hide)
  }

  function focusTalentUnlockStep(id) {
    const node = state.talents.find((item) => item.id === id)
    if (!node) return false
    revealTalentSearchMatch(id)
    focusTalentNodeById(id)
    markTalentUnlockStepFocus(id)
    flashTalentAction('', `已定位 ${node.name}`)
    trackWebsimEvent('websim_talent_unlock_step_focus', {
      classKey: state.classKey,
      specKey: state.specKey,
      heroKey: state.heroKey,
      talentId: id
    })
    return true
  }

  function applyTalentUnlockStepRank(id) {
    const node = state.talents.find((item) => item.id === id)
    if (!node) return false
    if (!canIncreaseTalent(node)) {
      focusTalentUnlockStep(id)
      flashTalentAction('', talentDisabledReason(node) || '这一步暂时不能加点', 'error')
      return false
    }
    const changed = applyTalentRankDelta(node, 1, { restoreFocus: true })
    trackWebsimEvent('websim_talent_unlock_step_add', {
      classKey: state.classKey,
      specKey: state.specKey,
      heroKey: state.heroKey,
      talentId: id,
      rank: rankFor(id),
      changed
    })
    return changed
  }

  function currentTalentSearchMatch(matches = talentSearchMatches()) {
    const index = normalizeTalentSearchIndex(matches)
    return matches[index] || null
  }

  function setTalentSearchIndexToId(id) {
    const matches = talentSearchMatches()
    if (!id || !matches.length) return false
    const index = matches.findIndex((node) => node.id === id)
    if (index < 0) return false
    state.talentSearchIndex = index
    return true
  }

  function revealTalentSearchMatch(id) {
    if (!root.document || !id) return false
    const node = Array.from(root.document.querySelectorAll('.talent-node'))
      .find((item) => item.dataset.talentId === id)
    if (!node || !node.scrollIntoView) return false
    node.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' })
    return true
  }

  function revealCurrentTalentSearchMatch(matches = talentSearchMatches()) {
    const match = currentTalentSearchMatch(matches)
    return match ? revealTalentSearchMatch(match.id) : false
  }

  function focusTalentSearchNode(id) {
    focusTalentNodeById(id)
  }

  function restoreTalentNodeFocus(id) {
    focusTalentNodeById(id)
    if (root.requestAnimationFrame) root.requestAnimationFrame(() => focusTalentNodeById(id))
    if (root.setTimeout) {
      root.setTimeout(() => focusTalentNodeById(id), 80)
      root.setTimeout(() => focusTalentNodeById(id), 320)
      root.setTimeout(() => focusTalentNodeById(id), 760)
    }
  }

  function restoreChoiceOptionFocus(id) {
    const node = state.talents.find((item) => item.id === id)
    if (!node || choiceDisabledReason(node)) return
    restoreTalentNodeFocus(id)
    if (root.setTimeout) root.setTimeout(() => restoreTalentNodeFocus(id), 140)
  }

  function focusTalentSearchInput(id) {
    const input = $(id) || $('talentSearchInput')
    if (!input) return
    input.focus()
    if (input.setSelectionRange) {
      const end = String(input.value || '').length
      input.setSelectionRange(end, end)
    }
  }

  function jumpTalentSearchMatch(direction) {
    const matches = talentSearchMatches()
    if (!matches.length) {
      flashTalentAction('', normalizedTalentSearchTerm() ? '没有匹配天赋' : '输入天赋名称搜索', normalizedTalentSearchTerm() ? 'error' : 'success')
      return
    }
    const current = normalizeTalentSearchIndex(matches)
    state.talentSearchIndex = (current + direction + matches.length) % matches.length
    const next = matches[state.talentSearchIndex]
    renderTalents()
    focusTalentSearchNode(next.id)
    flashTalentAction('', `匹配 ${state.talentSearchIndex + 1}/${matches.length}`)
  }

  function talentSearchInputClass() {
    return `text-field-input body-text ${state.talentSearchTerm ? 'open' : ''}`.trim()
  }

  function talentSearchPlaceholder() {
    return '搜索所有天赋'
  }

  function clearTalentSearch(focusId = '') {
    state.talentSearchTerm = ''
    state.talentSearchFocusId = focusId || ''
    state.talentSearchIndex = 0
    renderTalents()
    if (focusId) focusTalentSearchInput(focusId)
  }

  function talentFooterPanelMarkup() {
    const panel = state.footerMenuPanel || ''
    if (!panel) return ''
    const code = panel === 'share' ? buildTalentShareUrl() : buildTalentExportCode()
    if (panel === 'export' || panel === 'share') {
      const title = panel === 'share' ? '分享构筑' : '导出当前构筑'
      const buttonText = panel === 'share' ? '复制分享链接' : '复制导出字符串'
      const note = panel === 'share'
        ? '复制包含当前职业、专精、英雄天赋和已点天赋的深链接。'
        : '用这段字符串可以重新载入当前职业、专精、英雄天赋和已分配点数。'
      return `<div class="talent-footer-panel" data-footer-panel="${escapeHtml(panel)}">
        <div class="talent-footer-panel-title">
          <strong>${escapeHtml(title)}</strong>
          <button type="button" class="talent-footer-panel-close" data-talent-footer-panel-close aria-label="关闭">×</button>
        </div>
        <textarea class="talent-footer-panel-code" readonly>${escapeHtml(code)}</textarea>
        <p>${escapeHtml(note)}</p>
        <button type="button" class="talent-footer-panel-primary" data-talent-footer-action="${panel === 'share' ? 'copy-panel' : 'copy-export'}">${escapeHtml(buttonText)}</button>
      </div>`
    }
    if (panel === 'import') {
      const value = state.footerImportDraft || ($('talentInput') ? $('talentInput').value : '')
      return `<div class="talent-footer-panel" data-footer-panel="import">
        <div class="talent-footer-panel-title">
          <strong>导入构筑</strong>
          <button type="button" class="talent-footer-panel-close" data-talent-footer-panel-close aria-label="关闭">×</button>
        </div>
        <textarea id="talentFooterImportInput" class="talent-footer-panel-code" placeholder="粘贴 WebSim 构筑字符串">${escapeHtml(value)}</textarea>
        <p>粘贴构筑字符串后，将它导入当前天赋模拟器。</p>
        <button type="button" class="talent-footer-panel-primary" data-talent-footer-action="import-panel">导入构筑</button>
      </div>`
    }
    if (panel === 'character') {
      return `<div class="talent-footer-panel" data-footer-panel="character">
        <div class="talent-footer-panel-title">
          <strong>载入角色</strong>
          <button type="button" class="talent-footer-panel-close" data-talent-footer-panel-close aria-label="关闭">×</button>
        </div>
        <div class="talent-footer-character-fields">
          <input id="talentFooterCharacterRealm" type="text" placeholder="服务器">
          <input id="talentFooterCharacterName" type="text" placeholder="角色名">
        </div>
        <p>账号数据可用后，将通过当前 WebSim 角色档案同步载入。</p>
        <button type="button" class="talent-footer-panel-primary" data-talent-footer-action="character-panel">载入角色</button>
      </div>`
    }
    return ''
  }

  function pvpSelectionKey() {
    return `${state.classKey}:${state.specKey}`
  }

  function pvpSelectionsForCurrentSpec() {
    const key = pvpSelectionKey()
    const selections = Array.isArray(state.pvpSelections[key]) ? state.pvpSelections[key].slice(0, 3) : []
    while (selections.length < 3) selections.push('')
    return selections
  }

  function setPvpSelectionsForCurrentSpec(selections) {
    const next = (selections || []).slice(0, 3)
    while (next.length < 3) next.push('')
    state.pvpSelections[pvpSelectionKey()] = next
  }

  function pvpTalentOptions() {
    const specMeta = currentSpecMeta()
    const classMeta = currentClassMeta()
    const label = specMeta.label || specMeta.labelEn || classMeta.label || classMeta.labelEn || '专精'
    const sourceNodes = state.talents
      .filter((node) => node && node.id && node.name)
      .sort((a, b) => {
        const treeWeight = { spec: 0, class: 1, hero: 2 }
        return (treeWeight[talentTreeKey(a)] || 3) - (treeWeight[talentTreeKey(b)] || 3)
          || Number(a.row || 0) - Number(b.row || 0)
          || Number(a.col || 0) - Number(b.col || 0)
      })
    const seen = new Set()
    const options = []
    sourceNodes.forEach((node) => {
      const key = String(node.name || '').toLowerCase()
      if (!key || seen.has(key) || options.length >= 9) return
      seen.add(key)
      options.push({
        id: `${pvpSelectionKey()}:${node.id}`,
        name: node.name,
        iconUrl: node.iconUrl || specMeta.iconUrl || classMeta.iconUrl || '',
        description: node.description || `${label} 的 PvP 调整选项。`,
        sourceTree: talentTreeKey(node)
      })
    })
    const fallbackNames = ['控制反制', '竞技场耐久', '压制窗口', '反打手段', '决斗训练', '战场指挥']
    fallbackNames.forEach((name, index) => {
      if (options.length >= 9) return
      options.push({
        id: `${pvpSelectionKey()}:fallback-${index + 1}`,
        name: `${label} ${name}`,
        iconUrl: specMeta.iconUrl || classMeta.iconUrl || '',
        description: `${label} 面向竞技场和战场构筑的 PvP 选项。`,
        sourceTree: 'pvp'
      })
    })
    return options
  }

  function pvpOptionById(id) {
    return pvpTalentOptions().find((option) => option.id === id) || null
  }

  function selectedPvpOption(slotIndex) {
    return pvpOptionById(pvpSelectionsForCurrentSpec()[slotIndex] || '')
  }

  function pvpOptionTaken(optionId, slotIndex) {
    return pvpSelectionsForCurrentSpec().some((id, index) => index !== slotIndex && id === optionId)
  }

  function pvpTalentSlotMarkup(index) {
    const slotIndex = Math.max(0, Number(index || 1) - 1)
    const selectedOption = selectedPvpOption(slotIndex)
    const iconUrl = (selectedOption && selectedOption.iconUrl) || currentSpecMeta().iconUrl || currentClassMeta().iconUrl || ''
    const label = selectedOption ? `PvP 天赋槽位 ${index}：${selectedOption.name}` : `PvP 天赋槽位 ${index}`
    const icon = iconUrl
      ? `<span class="talent-footer-pvp-icon"><img src="${escapeHtml(iconUrl)}" alt=""></span>`
      : '<span class="talent-footer-pvp-icon"></span>'
    return `<button type="button" class="talent-footer-pvp-slot ${selectedOption ? 'selected' : ''} ${state.activePvpSlot === slotIndex ? 'open' : ''}" data-talent-footer-action="pvp" data-slot="${escapeHtml(index)}" aria-label="${escapeHtml(label)}" title="${escapeHtml(selectedOption ? selectedOption.name : '选择 PvP 天赋')}">
      ${icon}
      <span class="talent-footer-pvp-cover" aria-hidden="true"></span>
    </button>`
  }

  function pvpSlotIndexFromButton(button) {
    return Math.max(0, Math.min(2, Number(button && button.dataset.slot || 1) - 1))
  }

  function pvpSlotButtons(scope) {
    const rootScope = scope || root.document
    return rootScope ? Array.from(rootScope.querySelectorAll('.talent-footer-pvp-slot')) : []
  }

  function focusPvpSlotByDirection(button, direction) {
    const scope = button && button.closest ? button.closest('.talent-footer-pvp') : root.document
    const buttons = pvpSlotButtons(scope)
    if (!buttons.length) return false
    const currentIndex = Math.max(0, buttons.indexOf(button))
    const nextIndex = direction === 'home' ? 0
      : direction === 'end' ? buttons.length - 1
        : (currentIndex + (direction === 'next' ? 1 : -1) + buttons.length) % buttons.length
    if (buttons[nextIndex] && buttons[nextIndex].focus) buttons[nextIndex].focus()
    return true
  }

  function handlePvpSlotKeydown(event, button) {
    const key = event.key
    const slotIndex = pvpSlotIndexFromButton(button)
    const direction = key === 'ArrowRight' || key === 'ArrowDown' ? 'next'
      : key === 'ArrowLeft' || key === 'ArrowUp' ? 'prev'
        : key === 'Home' ? 'home'
          : key === 'End' ? 'end'
            : ''
    if (direction) {
      event.preventDefault()
      event.stopPropagation()
      hidePvpTalentPicker()
      focusPvpSlotByDirection(button, direction)
      return
    }
    if (key === 'Enter' || key === ' ') {
      event.preventDefault()
      event.stopPropagation()
      closeTalentFooterMenu()
      showPvpTalentPicker(slotIndex, button, event)
      return
    }
    if (key === 'Backspace' || key === 'Delete') {
      event.preventDefault()
      event.stopPropagation()
      if (!clearPvpTalent(slotIndex)) hidePvpTalentPicker()
      focusPvpSlot(slotIndex)
    }
  }

  function talentFooterMarkup() {
    const searchValue = escapeHtml(state.talentSearchTerm || '')
    return `<div class="talent-footer">
      <div class="talent-footer-inner">
        <div class="talent-footer-actions">
          <div class="talent-footer-export-menu">
            <button type="button" class="talent-footer-select" aria-expanded="false" data-talent-footer-menu>
              <span>载入 / 导出构筑</span>
              <span class="talent-footer-select-arrow" aria-hidden="true"></span>
            </button>
            <div class="talent-footer-menu" hidden>
              <div class="talent-footer-menu-col">
                <span class="talent-footer-menu-heading">WebSim 构筑</span>
                <button type="button" class="talent-footer-menu-item blizzard-blue" data-talent-footer-action="preset">${escapeHtml(currentSpecMeta().label || currentSpecMeta().labelEn || '当前')}入门构筑</button>
                <button type="button" class="talent-footer-menu-item blizzard-blue ${state.footerMenuPanel === 'export' ? 'active' : ''}" data-talent-footer-panel="export">导出当前构筑</button>
                <button type="button" class="talent-footer-menu-item blizzard-blue" data-talent-footer-action="clear">重置当前构筑</button>
              </div>
              <div class="talent-footer-menu-col">
                <button type="button" class="talent-footer-menu-item q1 ${state.footerMenuPanel === 'character' ? 'active' : ''}" data-talent-footer-panel="character">载入角色</button>
                <button type="button" class="talent-footer-menu-item q1 ${state.footerMenuPanel === 'import' ? 'active' : ''}" data-talent-footer-panel="import">导入</button>
                <button type="button" class="talent-footer-menu-item q1 ${state.footerMenuPanel === 'share' ? 'active' : ''}" data-talent-footer-panel="share">分享（复制到剪贴板）</button>
              </div>
              ${talentFooterPanelMarkup()}
            </div>
          </div>
          <div class="talent-footer-search">
            <input id="talentSearchInput" class="talent-footer-search-input ${escapeHtml(talentSearchInputClass())}" type="text" placeholder="${escapeHtml(talentSearchPlaceholder())}" value="${searchValue}" autocomplete="off" spellcheck="false">
            ${talentSearchControlsMarkup()}
            <button type="button" class="wh-button talent-footer-search-clear" data-talent-search-clear aria-label="清空搜索">×</button>
          </div>
        </div>
        <div class="talent-footer-pvp" aria-label="PvP 天赋">
          <span class="talent-footer-pvp-label">PvP 天赋：</span>
          ${[1, 2, 3].map(pvpTalentSlotMarkup).join('')}
        </div>
        <span class="talent-footer-frill talent-footer-frill-left" aria-hidden="true"></span>
        <span class="talent-footer-frill talent-footer-frill-right" aria-hidden="true"></span>
      </div>
    </div>`
  }

  function childNodesFor(node) {
    return state.talents.filter((item) => (item.parentIds || []).includes(node.id) && talentTreeKey(item) === talentTreeKey(node))
  }

  function relatedTalentIdsFor(node) {
    const related = new Set([node.id])
    const byId = new Map(state.talents.map((item) => [item.id, item]))
    const addParents = (item) => {
      ;(item.parentIds || []).forEach((parentId) => {
        const parent = byId.get(parentId)
        if (!parent || related.has(parent.id)) return
        related.add(parent.id)
        addParents(parent)
      })
    }
    addParents(node)
    childNodesFor(node).forEach((child) => related.add(child.id))
    return related
  }

  function talentPathContextFor(node) {
    const related = new Set([node.id])
    const ancestors = new Set()
    const descendants = new Set()
    const upstreamLinks = new Set()
    const downstreamLinks = new Set()
    const byId = new Map(state.talents.map((item) => [item.id, item]))
    const linkKey = (fromId, toId) => `${fromId}->${toId}`
    const addParents = (item) => {
      ;(item.parentIds || []).forEach((parentId) => {
        const parent = byId.get(parentId)
        if (!parent || talentTreeKey(parent) !== talentTreeKey(node)) return
        upstreamLinks.add(linkKey(parent.id, item.id))
        if (ancestors.has(parent.id)) return
        ancestors.add(parent.id)
        related.add(parent.id)
        addParents(parent)
      })
    }
    const addChildren = (item) => {
      childNodesFor(item).forEach((child) => {
        downstreamLinks.add(linkKey(item.id, child.id))
        if (descendants.has(child.id)) return
        descendants.add(child.id)
        related.add(child.id)
        addChildren(child)
      })
    }
    addParents(node)
    addChildren(node)
    return { ancestors, descendants, downstreamLinks, related, upstreamLinks }
  }

  function treeNodesFor(node) {
    const key = talentTreeKey(node)
    return state.talents.filter((item) => talentTreeKey(item) === key)
  }

  function talentGateCandidateNodesFor(node, limit = 4) {
    if (!node || pointRequirementSatisfied(node)) return []
    return treeNodesFor(node)
      .filter((item) => item.id !== node.id && rankFor(item) < maxRankFor(item) && canIncreaseTalent(item))
      .sort((a, b) => {
        const aRank = rankFor(a)
        const bRank = rankFor(b)
        return (bRank > 0 ? 1 : 0) - (aRank > 0 ? 1 : 0)
          || Number(a.row || 0) - Number(b.row || 0)
          || Number(a.col || 0) - Number(b.col || 0)
          || String(a.name || '').localeCompare(String(b.name || ''))
      })
      .slice(0, limit)
  }

  function talentBlockingContextFor(node) {
    const nodeIds = new Set()
    const links = new Set()
    if (!node) return { links, nodeIds }
    const linkKey = (fromId, toId) => `${fromId}->${toId}`
    const directParents = missingParentNodesFor(node)
    directParents.forEach((parent) => {
      nodeIds.add(parent.id)
      links.add(linkKey(parent.id, node.id))
      missingParentNodesFor(parent).slice(0, 2).forEach((grandParent) => {
        nodeIds.add(grandParent.id)
        links.add(linkKey(grandParent.id, parent.id))
      })
    })
    if (!pointRequirementSatisfied(node)) {
      talentGateCandidateNodesFor(node).forEach((candidate) => nodeIds.add(candidate.id))
    }
    if (!nodeIds.size && pointCapReached(node)) nodeIds.add(node.id)
    return { links, nodeIds }
  }

  function talentLinkEndpoints(from, to, metrics) {
    const cols = Math.max(1, Number(metrics.cols || 1))
    const rows = Math.max(1, Number(metrics.rows || 1))
    const x1 = ((Number(from.col || 1) - 0.5) / cols) * 100
    const y1 = ((Number(from.row || 1) - 0.5) / rows) * 100
    const x2 = ((Number(to.col || 1) - 0.5) / cols) * 100
    const y2 = ((Number(to.row || 1) - 0.5) / rows) * 100
    const dx = x2 - x1
    const dy = y2 - y1
    const distance = Math.hypot(dx, dy) || 1
    const cellStep = Math.min(100 / cols, 100 / rows)
    const offset = Math.min(cellStep * 0.3, Math.max(0, (distance - 0.01) / 2))
    const offsetX = (dx / distance) * offset
    const offsetY = (dy / distance) * offset
    return {
      x1: x1 + offsetX,
      y1: y1 + offsetY,
      x2: x2 - offsetX,
      y2: y2 - offsetY
    }
  }

  function talentLineMarkup(nodes, metrics) {
    const byId = new Map(nodes.map((node) => [node.id, node]))
    const blockedNode = activeBlockedTalentNode()
    const blockedRequiredIds = blockedNode ? missingRequiredTalentIdsFor(blockedNode) : new Set()
    const blockedPathContext = blockedNode ? talentBlockingContextFor(blockedNode) : null
    const blockedUnlockLinks = blockedPathContext ? blockedPathContext.links : new Set()
    const lineFor = (from, to) => {
      const endpoints = talentLinkEndpoints(from, to, metrics)
      const parentSelected = rankFor(from) > 0
      const childSelected = rankFor(to) > 0
      const parentReady = parentsSatisfied(to)
      const pointReady = pointRequirementSatisfied(to)
      const childAvailable = parentSelected && (childSelected || canIncreaseTalent(to))
      const linkState = parentSelected && childSelected ? 'active'
        : childAvailable ? 'available'
          : parentSelected && parentReady && !pointReady ? 'gate-locked'
            : parentReady ? 'idle'
              : 'locked'
      const attentionClass = blockedNode && blockedNode.id === to.id
        ? (!pointReady ? 'blocked-path' : (blockedRequiredIds.has(from.id) ? 'required-missing' : ''))
        : ''
      const unlockClass = blockedNode && blockedUnlockLinks.has(`${from.id}->${to.id}`) ? 'unlock-path' : ''
      const recent = state.recentTalentId && (from.id === state.recentTalentId || to.id === state.recentTalentId)
      const d = `M ${endpoints.x1.toFixed(2)} ${endpoints.y1.toFixed(2)} L ${endpoints.x2.toFixed(2)} ${endpoints.y2.toFixed(2)}`
      return `<path class="talent-link ${escapeHtml(linkState)} ${attentionClass} ${unlockClass} ${recent ? 'recent' : ''}" data-link-state="${escapeHtml(linkState)}" data-link-shape="edge" data-from="${escapeHtml(from.id)}" data-to="${escapeHtml(to.id)}" d="${d}"></path>`
    }
    return nodes.flatMap((node) =>
      (node.parentIds || []).map((parentId) => byId.get(parentId)).filter(Boolean).map((parent) => lineFor(parent, node))
    ).join('')
  }

  function talentGateMarkup(nodes, metrics) {
    const gates = gateRequirementsForNodes(nodes)
    const blockedNode = activeBlockedTalentNode()
    const blockedTreeKey = blockedNode ? talentTreeKey(blockedNode) : ''
    const blockedRequirement = blockedNode && !pointRequirementSatisfied(blockedNode)
      ? pointRequirementFor(blockedNode)
      : 0
    return gates.map((gate) => {
      const rows = Math.max(1, Number(metrics.rows || 1))
      const top = Math.max(0, Math.min(100, ((gate.row - 1) / rows) * 100))
      const treeKey = nodes && nodes[0] ? talentTreeKey(nodes[0]) : ''
      const spent = treeKey ? talentPoints(treeKey) : 0
      const satisfied = spent >= gate.requirement
      const remaining = Math.max(0, gate.requirement - spent)
      const label = `${gate.requirement} 点`
      const detail = satisfied ? '已开启' : `还差 ${remaining} 点`
      const attention = treeKey && treeKey === blockedTreeKey && gate.requirement === blockedRequirement
      return `<div class="talent-gate ${satisfied ? 'satisfied' : 'locked'} ${attention ? 'attention' : ''}" data-gate-state="${satisfied ? 'unlocked' : 'locked'}" style="--gate-top:${top.toFixed(2)}%;" aria-label="${escapeHtml(label)}门槛 ${escapeHtml(detail)}"><span>${escapeHtml(label)}<small>${escapeHtml(detail)}</small></span></div>`
    }).join('')
  }

  function talentNodeButtonMeta(button) {
    return {
      id: button && (button.dataset.talentId || button.dataset.id || ''),
      tree: button && (button.dataset.treeKey || ''),
      row: Math.max(1, Number(button && button.dataset.row || 1)),
      col: Math.max(1, Number(button && button.dataset.col || 1))
    }
  }

  function orderedTalentNodeButtons(treeKey = '') {
    if (!root.document) return []
    return Array.from(root.document.querySelectorAll('.talent-node'))
      .filter((button) => !treeKey || (button.dataset.treeKey || '') === treeKey)
      .sort((a, b) => {
        const left = talentNodeButtonMeta(a)
        const right = talentNodeButtonMeta(b)
        return left.row - right.row || left.col - right.col || left.id.localeCompare(right.id)
      })
  }

  function focusTalentNodeButton(button) {
    if (!button) return false
    if (button.scrollIntoView) button.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' })
    if (button.focus) button.focus({ preventScroll: true })
    return true
  }

  function nearestTalentNodeButton(currentButton, direction) {
    const current = talentNodeButtonMeta(currentButton)
    const buttons = orderedTalentNodeButtons(current.tree).filter((button) => button !== currentButton)
    const candidates = buttons.map((button) => {
      const next = talentNodeButtonMeta(button)
      const rowDelta = next.row - current.row
      const colDelta = next.col - current.col
      const forward = direction === 'right' ? colDelta > 0
        : direction === 'left' ? colDelta < 0
          : direction === 'down' ? rowDelta > 0
            : rowDelta < 0
      if (!forward) return null
      const primary = direction === 'right' || direction === 'left' ? Math.abs(colDelta) : Math.abs(rowDelta)
      const secondary = direction === 'right' || direction === 'left' ? Math.abs(rowDelta) : Math.abs(colDelta)
      return { button, score: primary * 100 + secondary }
    }).filter(Boolean).sort((a, b) => a.score - b.score)
    return candidates[0] ? candidates[0].button : null
  }

  function focusTalentNodeByDirection(currentButton, direction) {
    if (!currentButton) return false
    const current = talentNodeButtonMeta(currentButton)
    const buttons = orderedTalentNodeButtons(current.tree)
    if (!buttons.length) return false
    const target = direction === 'home' ? buttons[0]
      : direction === 'end' ? buttons[buttons.length - 1]
        : nearestTalentNodeButton(currentButton, direction)
    return focusTalentNodeButton(target || currentButton)
  }

  function decrementTalentNodeRank(node, restoreFocus = false) {
    return applyTalentRankDelta(node, -1, { restoreFocus })
  }

  function talentRankChangeMessage(node, delta, before, next) {
    if (!node) return ''
    const maxRank = maxRankFor(node)
    if (next === before) {
      if (delta > 0 && before >= maxRank) return `已达满级（${before}/${maxRank}）`
      return delta < 0 ? '没有可移除的点数' : (talentDisabledReason(node) || '点数未变化')
    }
    if (delta < 0) return `已移除 1 点（${next}/${maxRank}）`
    return next >= maxRank ? `已达满级（${next}/${maxRank}）` : `已加入 1 点（${next}/${maxRank}）`
  }

  function applyTalentRankDelta(node, delta, options = {}) {
    if (!node) return false
    const id = node.id
    const restoreFocus = Boolean(options.restoreFocus)
    const historySnapshot = talentBuildSnapshot()
    const beforeSignature = talentBuildSnapshotSignature(historySnapshot)
    const before = rankFor(id)
    const next = adjustTalentRank(id, delta)
    const changed = talentBuildSnapshotSignature() !== beforeSignature
    if (changed) pushTalentHistorySnapshot(historySnapshot)
    if (next !== before) markRecentTalent(id, delta < 0 ? 'remove' : 'add')
    if (changed) {
      const clearedBlockedFeedback = clearResolvedBlockedTalentFeedback()
      if (!clearedBlockedFeedback && state.blockedTalentId) scheduleBlockedTalentFeedbackClear()
    }
    hideChoicePicker()
    renderTalents()
    if (changed) {
      renderProfilePreview()
      syncLiveTalentRoute()
    }
    if (restoreFocus) restoreTalentNodeFocus(id)
    flashTalentAction('', talentRankChangeMessage(node, delta, before, next), next === before ? 'error' : 'success')
    return next !== before
  }

  function handleTalentNodeKeydown(event, node, button) {
    const key = event.key
    const direction = key === 'ArrowRight' ? 'right'
      : key === 'ArrowLeft' ? 'left'
        : key === 'ArrowDown' ? 'down'
          : key === 'ArrowUp' ? 'up'
            : key === 'Home' ? 'home'
              : key === 'End' ? 'end'
                : ''
    if (direction) {
      event.preventDefault()
      hideChoicePicker()
      focusTalentNodeByDirection(button, direction)
      return
    }
    if (key === 'Escape' && state.talentSearchTerm) {
      event.preventDefault()
      event.stopPropagation()
      hideChoicePicker()
      focusTalentSearchInput(state.talentSearchFocusId || 'talentSearchInput')
      return
    }
    const activatesNode = key === 'Enter' || key === ' '
    if (key === 'Backspace' || key === 'Delete' || (activatesNode && event.shiftKey)) {
      event.preventDefault()
      event.stopPropagation()
      decrementTalentNodeRank(node, true)
      return
    }
    if (activatesNode) {
      event.preventDefault()
      event.stopPropagation()
      if (button && button.click) button.click()
    }
  }

  function setTalentHoverState(node, active) {
    const tree = $('talentTree')
    if (!tree) return
    const focusNodes = active && node && node.choiceGroup ? choiceGroupNodes(node) : (active && node ? [node] : [])
    const related = new Set()
    const ancestors = new Set()
    const choiceRelated = new Set()
    const descendants = new Set()
    const downstreamLinks = new Set()
    const upstreamLinks = new Set()
    focusNodes.forEach((focusNode) => {
      const context = talentPathContextFor(focusNode)
      context.related.forEach((id) => related.add(id))
      context.ancestors.forEach((id) => ancestors.add(id))
      context.descendants.forEach((id) => descendants.add(id))
      context.upstreamLinks.forEach((id) => upstreamLinks.add(id))
      context.downstreamLinks.forEach((id) => downstreamLinks.add(id))
      if (node && node.choiceGroup && focusNode.id !== node.id) choiceRelated.add(focusNode.id)
    })
    tree.querySelectorAll('.talent-node').forEach((button) => {
      const id = button.dataset.id || ''
      const isRelated = related.has(button.dataset.id || '')
      button.classList.toggle('hovered', active && id === node.id)
      button.classList.toggle('ancestor-related', active && ancestors.has(id) && id !== node.id)
      button.classList.toggle('choice-related', active && choiceRelated.has(id))
      button.classList.toggle('descendant-related', active && descendants.has(id) && id !== node.id)
      button.classList.toggle('related', active && isRelated && id !== node.id)
      button.classList.toggle('dimmed', active && !isRelated)
    })
    tree.querySelectorAll('.talent-link').forEach((line) => {
      const from = line.getAttribute('data-from') || ''
      const to = line.getAttribute('data-to') || ''
      const linkId = `${from}->${to}`
      const upstream = upstreamLinks.has(linkId)
      const downstream = downstreamLinks.has(linkId)
      const inPath = upstream || downstream
      line.classList.toggle('hover-path', active && inPath)
      line.classList.toggle('upstream-path', active && upstream)
      line.classList.toggle('downstream-path', active && downstream)
      line.classList.toggle('dimmed', active && !inPath)
    })
  }

  function talentTooltip() {
    if (!root.document) return null
    let tooltip = $('talentTooltip')
    if (!tooltip) {
      tooltip = root.document.createElement('div')
      tooltip.id = 'talentTooltip'
      tooltip.className = 'talent-tooltip'
      root.document.body.appendChild(tooltip)
    }
    return tooltip
  }

  function talentChoicePicker() {
    if (!root.document) return null
    let picker = $('talentChoicePicker')
    if (!picker) {
      picker = root.document.createElement('div')
      picker.id = 'talentChoicePicker'
      picker.className = 'talent-choice-picker'
      picker.setAttribute('role', 'menu')
      picker.setAttribute('aria-label', '选择一个天赋')
      picker.setAttribute('aria-hidden', 'true')
      picker.addEventListener('keydown', handleChoicePickerKeydown)
      root.document.body.appendChild(picker)
    }
    return picker
  }

  function isChoicePickerVisible() {
    const picker = $('talentChoicePicker')
    return Boolean(picker && picker.classList.contains('visible'))
  }

  function choiceGroupNodes(node) {
    if (!node.choiceGroup) return []
    return state.talents
      .filter((item) => item.choiceGroup === node.choiceGroup && talentTreeKey(item) === talentTreeKey(node))
      .sort((a, b) => Number(a.row || 0) - Number(b.row || 0)
        || Number(a.col || 0) - Number(b.col || 0)
        || Number(a.traitId || 0) - Number(b.traitId || 0)
        || String(a.name || '').localeCompare(String(b.name || '')))
  }

  function choiceGroupLabel(node, group = choiceGroupNodes(node)) {
    return group.length > 1 ? `${group.length}选1` : ''
  }

  function choiceNodeSpread(node, group = choiceGroupNodes(node)) {
    if (!node || group.length < 2) return { index: 0, x: 0, y: 0 }
    const index = Math.max(0, group.findIndex((item) => item.id === node.id))
    const sameCell = group.every((item) =>
      Number(item.row || 0) === Number(node.row || 0)
      && Number(item.col || 0) === Number(node.col || 0))
    if (!sameCell) return { index, x: 0, y: 0 }
    const gap = group.length === 2 ? 30 : 24
    return {
      index,
      x: (index - ((group.length - 1) / 2)) * gap,
      y: group.length > 2 ? (index % 2 ? 5 : -5) : 0
    }
  }

  function choiceNodeBadgeMarkup(node, group = choiceGroupNodes(node)) {
    const label = choiceGroupLabel(node, group)
    if (!label) return ''
    return `<span class="talent-choice-badge" aria-hidden="true">${escapeHtml(label)}</span>`
  }

  function talentChoiceGroupMarkup(nodes, metrics) {
    const groups = new Map()
    ;(nodes || []).forEach((node) => {
      if (!node.choiceGroup) return
      const key = `${talentTreeKey(node)}:${node.choiceGroup}`
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key).push(node)
    })
    const cols = Math.max(1, Number(metrics.cols || 1))
    const rows = Math.max(1, Number(metrics.rows || 1))
    return Array.from(groups.values())
      .filter((group) => group.length > 1)
      .map((group) => {
        const sorted = sortTalentRouteNodes(group)
        const minCol = Math.min(...sorted.map((item) => Number(item.col || 1)))
        const maxCol = Math.max(...sorted.map((item) => Number(item.col || 1)))
        const minRow = Math.min(...sorted.map((item) => Number(item.row || 1)))
        const maxRow = Math.max(...sorted.map((item) => Number(item.row || 1)))
        const left = ((minCol - 0.82) / cols) * 100
        const right = (1 - ((maxCol - 0.18) / cols)) * 100
        const top = ((minRow - 0.78) / rows) * 100
        const bottom = (1 - ((maxRow - 0.1) / rows)) * 100
        const label = `${sorted.length}选1`
        const selected = sorted.find((item) => rankFor(item) > 0)
        return `<div class="talent-choice-group" data-choice-group-frame style="--choice-left:${left.toFixed(2)}%;--choice-right:${right.toFixed(2)}%;--choice-top:${top.toFixed(2)}%;--choice-bottom:${bottom.toFixed(2)}%;" aria-hidden="true">
          <span>${escapeHtml(label)}</span>
          ${selected ? `<em>${escapeHtml(selected.name)}</em>` : ''}
        </div>`
      }).join('')
  }

  function selectedChoicePeerFor(node) {
    return choiceGroupNodes(node).find((item) => rankFor(item) > 0) || null
  }

  function activeChoiceNode() {
    return state.activeChoiceNodeId
      ? state.talents.find((item) => item.id === state.activeChoiceNodeId)
      : null
  }

  function previewChoiceOption(id) {
    const node = state.talents.find((item) => item.id === id)
    if (!node) return
    setTalentHoverState(node, true)
  }

  function restoreChoicePickerHover() {
    const node = activeChoiceNode()
    if (node && isChoicePickerVisible()) setTalentHoverState(node, true)
  }

  function choicePickerOptions() {
    const picker = $('talentChoicePicker')
    return picker ? Array.from(picker.querySelectorAll('.talent-choice-option')) : []
  }

  function focusChoicePickerOption(option, offset) {
    const options = choicePickerOptions()
    if (!options.length) return
    const activeIndex = Math.max(0, options.indexOf(option))
    const nextIndex = (activeIndex + offset + options.length) % options.length
    options[nextIndex].focus()
  }

  function focusChoicePickerInitial() {
    const options = choicePickerOptions()
    if (!options.length) return
    const selected = options.find((option) => option.classList.contains('selected'))
    const available = options.find((option) => option.getAttribute('aria-disabled') !== 'true')
    ;(selected || available || options[0]).focus()
  }

  function focusActiveChoiceButton(id) {
    if (!root.document || !id) return
    const button = Array.from(root.document.querySelectorAll('.talent-node'))
      .find((item) => item.dataset.talentId === id)
    if (button && button.focus) button.focus()
  }

  function hideChoicePickerFromKeyboard() {
    const id = state.activeChoiceNodeId
    hideChoicePicker()
    focusActiveChoiceButton(id)
  }

  function handleChoicePickerKeydown(event) {
    const option = event.target && event.target.closest
      ? event.target.closest('.talent-choice-option')
      : null
    if (!option && event.key !== 'Escape') return
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault()
      focusChoicePickerOption(option, 1)
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault()
      focusChoicePickerOption(option, -1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      const options = choicePickerOptions()
      if (options[0]) options[0].focus()
    } else if (event.key === 'End') {
      event.preventDefault()
      const options = choicePickerOptions()
      if (options.length) options[options.length - 1].focus()
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      event.stopPropagation()
      const choiceId = option.dataset.choiceOption || ''
      chooseChoiceOption(choiceId, true)
      restoreChoiceOptionFocus(choiceId)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      hideChoicePickerFromKeyboard()
    }
  }

  function talentRequiresLabel(node) {
    const section = treeSectionForNode(node)
    if (section.key === 'class') return currentClassMeta().label || currentClassMeta().labelEn || '职业'
    if (section.key === 'hero') return currentHeroMeta().label || section.title || '英雄天赋'
    return currentSpecMeta().label || currentSpecMeta().labelEn || section.title || '专精'
  }

  function choiceDisabledReason(node) {
    if (rankFor(node) > 0) return ''
    const parents = parentNodesFor(node)
    if (!parentsSatisfied(node)) {
      const parentNames = parents.map((parent) => parent.name).join(' / ')
      return parentNames ? `需要 ${parentNames}` : '未解锁'
    }
    if (!pointRequirementSatisfied(node)) {
      const section = treeSectionForNode(node)
      return `需要先在 ${section.title || section.titleEn || talentTreeKey(node)} 投入 ${pointRequirementFor(node)} 点`
    }
    if (pointCapReached(node) && !selectedChoicePeerFor(node)) return '点数上限已满'
    return ''
  }

  function choiceDisabledState(node) {
    if (!choiceDisabledReason(node)) return ''
    if (!parentsSatisfied(node)) return 'missing-parent'
    if (!pointRequirementSatisfied(node)) return 'gate-locked'
    if (pointCapReached(node)) return 'capped'
    return 'locked'
  }

  function choicePickerOptionHtml(node) {
    const rank = rankFor(node)
    const maxRank = maxRankFor(node)
    const selected = rank > 0
    const disabledReason = choiceDisabledReason(node)
    const disabled = Boolean(disabledReason)
    const disabledState = choiceDisabledState(node)
    const optionState = selected ? 'selected' : (disabledState || 'available')
    const icon = node.iconUrl
      ? `<span class="tooltip-icon"><img src="${escapeHtml(node.iconUrl)}" alt=""></span>`
      : `<span class="tooltip-icon tooltip-icon-initial">${escapeHtml(String(node.name || '?').slice(0, 1))}</span>`
    const rankLine = maxRank > 1 || rank > 0
      ? `<span class="tooltip-rank-line">等级 ${escapeHtml(rank)}/${escapeHtml(maxRank)}</span>`
      : ''
    const status = selected ? '已选择'
      : disabled ? disabledReason
        : '点击选择'
    return `<button type="button" class="talent-choice-option ${selected ? 'selected' : ''} ${disabled ? 'disabled' : ''} ${disabledState}" data-choice-option="${escapeHtml(node.id)}" data-choice-option-state="${escapeHtml(optionState)}" role="menuitem" aria-pressed="${selected ? 'true' : 'false'}" aria-disabled="${disabled ? 'true' : 'false'}">
      ${icon}
      <span class="tooltip-title">${escapeHtml(node.name)}</span>
      <span class="tooltip-topline"><span>天赋</span>${rankLine}</span>
      <span class="tooltip-topline"><span>瞬发</span></span>
      <span class="tooltip-requires">需要 ${escapeHtml(talentRequiresLabel(node))}</span>
      <span class="tooltip-description">${escapeHtml(node.description || '暂未同步法术说明。')}</span>
      <span class="talent-choice-status">${escapeHtml(status)}</span>
    </button>`
  }

  function choicePickerHeaderHtml(node, options) {
    const selectedPeer = selectedChoicePeerFor(node)
    const title = selectedPeer ? '切换已选天赋' : '选择一个天赋'
    const detail = `该选择节点共有 ${options.length} 个选项`
    return `<div class="talent-choice-picker-header" aria-hidden="true">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(detail)}</span>
    </div>`
  }

  function moveChoicePicker(anchorElement) {
    const picker = talentChoicePicker()
    if (!picker || !anchorElement || !anchorElement.getBoundingClientRect) return
    const anchor = anchorElement.getBoundingClientRect()
    const pickerRect = picker.getBoundingClientRect ? picker.getBoundingClientRect() : { width: 354, height: 260 }
    const viewportWidth = Math.max(0, root.innerWidth || (root.document && root.document.documentElement.clientWidth) || 0)
    const viewportHeight = Math.max(0, root.innerHeight || (root.document && root.document.documentElement.clientHeight) || 0)
    const margin = 10
    const gap = 10
    const iconOffset = 54
    const pickerWidth = Math.max(260, pickerRect.width || 374)
    const cardWidth = Math.max(220, pickerWidth - iconOffset)
    const pickerHeight = Math.max(120, pickerRect.height || 260)
    const flipX = viewportWidth > 0 && anchor.right + gap + cardWidth + margin > viewportWidth
    let left = flipX ? anchor.left - gap - cardWidth : anchor.right + gap - iconOffset
    let top = anchor.top - pickerHeight - 8
    const flipY = top < margin
    if (flipY) top = anchor.bottom + 8
    if (viewportWidth > 0) left = Math.max(margin, Math.min(viewportWidth - pickerWidth - margin, left))
    if (viewportHeight > 0) top = Math.max(margin, Math.min(viewportHeight - pickerHeight - margin, top))
    picker.classList.toggle('flip-x', flipX)
    picker.classList.toggle('flip-y', flipY)
    picker.style.left = `${left}px`
    picker.style.top = `${top}px`
  }

  function hideChoicePicker() {
    const picker = $('talentChoicePicker')
    state.activeChoiceNodeId = ''
    setTalentHoverState(null, false)
    if (root.document) {
      root.document.querySelectorAll('.talent-node.choice-open').forEach((item) => item.classList.remove('choice-open'))
    }
    if (!picker) return
    picker.classList.remove('visible', 'flip-x', 'flip-y')
    picker.setAttribute('aria-hidden', 'true')
    picker.innerHTML = ''
  }

  function choiceBlockedTalentFeedback(node, restoreFocus = false) {
    const reason = choiceDisabledReason(node)
    if (!reason) return false
    setBlockedTalentFeedback(node)
    trackWebsimEvent('websim_talent_choice_blocked', {
      classKey: state.classKey,
      specKey: state.specKey,
      heroKey: state.heroKey,
      talentId: node.id,
      choiceGroup: node.choiceGroup || '',
      reason
    })
    renderTalents()
    if (restoreFocus) restoreTalentNodeFocus(node.id)
    return true
  }

  function chooseChoiceOption(id, restoreFocus = false) {
    const node = state.talents.find((item) => item.id === id)
    if (!node) return
    if (choiceDisabledReason(node)) {
      choiceBlockedTalentFeedback(node, restoreFocus)
      return
    }
    if (restoreFocus) setTalentSearchIndexToId(id)
    const historySnapshot = talentBuildSnapshot()
    const beforeSignature = talentBuildSnapshotSignature(historySnapshot)
    const before = rankFor(node)
    if (before <= 0) adjustTalentRank(id, 1)
    if (talentBuildSnapshotSignature() !== beforeSignature) pushTalentHistorySnapshot(historySnapshot)
    markRecentTalent(id)
    trackWebsimEvent('websim_talent_choice_select', {
      classKey: state.classKey,
      specKey: state.specKey,
      heroKey: state.heroKey,
      talentId: id,
      choiceGroup: node.choiceGroup || ''
    })
    hideChoicePicker()
    renderTalents()
    renderProfilePreview()
    syncLiveTalentRoute()
    if (restoreFocus) restoreTalentNodeFocus(id)
    flashTalentAction('', before > 0 ? '已保留当前选择' : '已选择天赋')
  }

  function showChoicePicker(node, event, anchorElement) {
    const options = choiceGroupNodes(node)
    if (!node.choiceGroup || options.length < 2) return false
    const picker = talentChoicePicker()
    if (!picker) return false
    if (root.document) {
      root.document.querySelectorAll('.talent-node.choice-open').forEach((item) => item.classList.remove('choice-open'))
    }
    state.activeChoiceNodeId = node.id
    hideTalentTooltip()
    setTalentHoverState(node, true)
    picker.innerHTML = `${choicePickerHeaderHtml(node, options)}
      <div class="talent-choice-picker-options">
        ${options.map(choicePickerOptionHtml).join('')}
      </div>`
    picker.classList.add('visible')
    picker.setAttribute('aria-hidden', 'false')
    picker.querySelectorAll('.talent-choice-option').forEach((option) => {
      option.addEventListener('pointerenter', () => previewChoiceOption(option.dataset.choiceOption || ''))
      option.addEventListener('mouseenter', () => previewChoiceOption(option.dataset.choiceOption || ''))
      option.addEventListener('focus', () => previewChoiceOption(option.dataset.choiceOption || ''))
      option.addEventListener('blur', restoreChoicePickerHover)
      option.addEventListener('click', (clickEvent) => {
        clickEvent.preventDefault()
        clickEvent.stopPropagation()
        const choiceId = option.dataset.choiceOption || ''
        chooseChoiceOption(choiceId, true)
        restoreChoiceOptionFocus(choiceId)
      })
    })
    const optionsPanel = picker.querySelector('.talent-choice-picker-options')
    if (optionsPanel) {
      optionsPanel.addEventListener('pointerleave', restoreChoicePickerHover)
      optionsPanel.addEventListener('mouseleave', restoreChoicePickerHover)
    }
    if (anchorElement) anchorElement.classList.add('choice-open')
    moveChoicePicker(anchorElement || (event && event.currentTarget))
    if (event && Number(event.detail || 0) === 0) focusChoicePickerInitial()
    return true
  }

  function hideChoicePickerOutside(event) {
    const picker = $('talentChoicePicker')
    if (!picker || !picker.classList.contains('visible')) return
    const target = event && event.target
    if (target && target.closest && (target.closest('.talent-choice-picker') || target.closest('.talent-node.choice'))) return
    hideChoicePicker()
  }

  function pvpTalentPicker() {
    if (!root.document) return null
    let picker = $('talentPvpPicker')
    if (!picker) {
      picker = root.document.createElement('div')
      picker.id = 'talentPvpPicker'
      picker.className = 'talent-pvp-picker'
      picker.setAttribute('role', 'menu')
      picker.setAttribute('aria-hidden', 'true')
      picker.addEventListener('keydown', handlePvpPickerKeydown)
      root.document.body.appendChild(picker)
    }
    return picker
  }

  function pvpPickerOptionHtml(option, slotIndex) {
    const selected = pvpSelectionsForCurrentSpec()[slotIndex] === option.id
    const taken = pvpOptionTaken(option.id, slotIndex)
    const disabled = taken && !selected
    const icon = option.iconUrl
      ? `<span class="talent-pvp-option-icon"><img src="${escapeHtml(option.iconUrl)}" alt=""></span>`
      : '<span class="talent-pvp-option-icon"></span>'
    const source = option.sourceTree === 'class' ? '职业 PvP' : option.sourceTree === 'hero' ? '英雄 PvP' : option.sourceTree === 'spec' ? '专精 PvP' : 'PvP'
    return `<button type="button" class="talent-pvp-option ${selected ? 'selected' : ''} ${disabled ? 'disabled' : ''}" data-pvp-option="${escapeHtml(option.id)}" role="menuitem" ${disabled ? 'disabled aria-disabled="true"' : ''}>
      ${icon}
      <span class="talent-pvp-option-copy">
        <strong>${escapeHtml(option.name)}</strong>
        <small>${escapeHtml(source)}</small>
        <span>${escapeHtml(option.description)}</span>
      </span>
    </button>`
  }

  function pvpPickerOptions() {
    const picker = $('talentPvpPicker')
    return picker ? Array.from(picker.querySelectorAll('.talent-pvp-option:not([disabled])')) : []
  }

  function focusPvpPickerOption(option, offset) {
    const options = pvpPickerOptions()
    if (!options.length) return
    const activeIndex = Math.max(0, options.indexOf(option))
    const nextIndex = (activeIndex + offset + options.length) % options.length
    options[nextIndex].focus()
  }

  function focusPvpPickerInitial() {
    const options = pvpPickerOptions()
    if (!options.length) return
    const selected = options.find((option) => option.classList.contains('selected'))
    ;(selected || options[0]).focus()
  }

  function focusPvpSlot(slotIndex) {
    if (!root.document || slotIndex < 0) return
    const slot = root.document.querySelector(`.talent-footer-pvp-slot[data-slot="${slotIndex + 1}"]`)
    if (slot && slot.focus) slot.focus()
  }

  function hidePvpTalentPickerFromKeyboard() {
    const slotIndex = state.activePvpSlot
    hidePvpTalentPicker()
    focusPvpSlot(slotIndex)
  }

  function handlePvpPickerKeydown(event) {
    const option = event.target && event.target.closest
      ? event.target.closest('.talent-pvp-option')
      : null
    if (!option && !['Escape', 'Backspace', 'Delete'].includes(event.key)) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault()
      focusPvpPickerOption(option, 1)
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault()
      focusPvpPickerOption(option, -1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      const options = pvpPickerOptions()
      if (options[0]) options[0].focus()
    } else if (event.key === 'End') {
      event.preventDefault()
      const options = pvpPickerOptions()
      if (options.length) options[options.length - 1].focus()
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      event.stopPropagation()
      selectPvpTalent(state.activePvpSlot, option.dataset.pvpOption || '', true)
    } else if (event.key === 'Backspace' || event.key === 'Delete') {
      event.preventDefault()
      event.stopPropagation()
      clearPvpTalent(state.activePvpSlot, true) || hidePvpTalentPickerFromKeyboard()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      hidePvpTalentPickerFromKeyboard()
    }
  }

  function movePvpTalentPicker(anchorElement) {
    const picker = pvpTalentPicker()
    if (!picker || !anchorElement || !anchorElement.getBoundingClientRect) return
    const rect = anchorElement.getBoundingClientRect()
    const width = 360
    const viewportWidth = root.innerWidth || root.document.documentElement.clientWidth || 1280
    const viewportHeight = root.innerHeight || root.document.documentElement.clientHeight || 800
    let left = rect.left + rect.width / 2 - width / 2
    let top = rect.bottom + 8
    if (left + width > viewportWidth - 12) left = viewportWidth - width - 12
    if (left < 12) left = 12
    const estimatedHeight = Math.min(480, 82 + pvpTalentOptions().length * 64)
    if (top + estimatedHeight > viewportHeight - 12) top = Math.max(12, rect.top - estimatedHeight - 8)
    picker.style.left = `${Math.round(left)}px`
    picker.style.top = `${Math.round(top)}px`
  }

  function hidePvpTalentPicker() {
    const picker = $('talentPvpPicker')
    state.activePvpSlot = -1
    if (!picker) return
    picker.classList.remove('visible')
    picker.setAttribute('aria-hidden', 'true')
    picker.innerHTML = ''
    root.document.querySelectorAll('.talent-footer-pvp-slot.open').forEach((button) => button.classList.remove('open'))
  }

  function selectPvpTalent(slotIndex, optionId, restoreFocus = false) {
    if (pvpOptionTaken(optionId, slotIndex)) return false
    const selections = pvpSelectionsForCurrentSpec()
    if (selections[slotIndex] === optionId) return false
    const historySnapshot = talentBuildSnapshot()
    selections[slotIndex] = optionId
    setPvpSelectionsForCurrentSpec(selections)
    pushTalentHistorySnapshot(historySnapshot)
    hidePvpTalentPicker()
    renderTalents()
    renderProfilePreview()
    syncLiveTalentRoute()
    flashTalentAction('', '已选择 PvP 天赋')
    if (restoreFocus) focusPvpSlot(slotIndex)
    return true
  }

  function clearPvpTalent(slotIndex, restoreFocus = false) {
    const selections = pvpSelectionsForCurrentSpec()
    if (!selections[slotIndex]) return false
    const historySnapshot = talentBuildSnapshot()
    selections[slotIndex] = ''
    setPvpSelectionsForCurrentSpec(selections)
    pushTalentHistorySnapshot(historySnapshot)
    hidePvpTalentPicker()
    renderTalents()
    renderProfilePreview()
    syncLiveTalentRoute()
    flashTalentAction('', '已清空 PvP 天赋')
    if (restoreFocus) focusPvpSlot(slotIndex)
    return true
  }

  function showPvpTalentPicker(slotIndex, anchorElement, event) {
    const picker = pvpTalentPicker()
    if (!picker) return false
    state.activePvpSlot = slotIndex
    const options = pvpTalentOptions()
    picker.innerHTML = `<div class="talent-pvp-picker-title">
        <strong>PvP 天赋</strong>
        <span>槽位 ${escapeHtml(slotIndex + 1)}</span>
      </div>
      <div class="talent-pvp-picker-options">
        ${options.map((option) => pvpPickerOptionHtml(option, slotIndex)).join('')}
      </div>
      <button type="button" class="talent-pvp-clear" data-pvp-clear="${escapeHtml(slotIndex)}">清空槽位</button>`
    picker.classList.add('visible')
    picker.setAttribute('aria-hidden', 'false')
    root.document.querySelectorAll('.talent-footer-pvp-slot.open').forEach((button) => button.classList.remove('open'))
    if (anchorElement) anchorElement.classList.add('open')
    picker.querySelectorAll('[data-pvp-option]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        selectPvpTalent(slotIndex, button.dataset.pvpOption || '')
      })
    })
    picker.querySelector('[data-pvp-clear]')?.addEventListener('click', (event) => {
      event.preventDefault()
      event.stopPropagation()
      clearPvpTalent(slotIndex) || hidePvpTalentPicker()
    })
    movePvpTalentPicker(anchorElement)
    if (event && Number(event.detail || 0) === 0) focusPvpPickerInitial()
    return true
  }

  function hidePvpTalentPickerOutside(event) {
    const picker = $('talentPvpPicker')
    if (!picker || !picker.classList.contains('visible')) return
    const target = event && event.target
    if (target && target.closest && (target.closest('.talent-pvp-picker') || target.closest('.talent-footer-pvp-slot'))) return
    hidePvpTalentPicker()
  }

  function talentTooltipHtml(node) {
    const rank = rankFor(node)
    const maxRank = maxRankFor(node)
    const section = treeSectionForNode(node)
    const parents = parentNodesFor(node)
    const locked = !parentsSatisfied(node)
    const requirement = pointRequirementFor(node)
    const availablePoints = pointsAvailableForRequirement(node)
    const gated = !pointRequirementSatisfied(node)
    const pointCap = pointCapFor(node)
    const treePoints = talentPoints(talentTreeKey(node))
    const capped = pointCapReached(node) && rank < maxRank
    const parentNames = parents.map((parent) => parent.name).join(' / ')
    const choices = choiceGroupNodes(node).filter((item) => item.id !== node.id).map((item) => item.name).join(' / ')
    const learned = rank >= maxRank
    const status = learned ? '已点满'
      : capped ? '点数上限已满'
        : rank > 0 ? '已投入部分点数'
          : locked || gated ? '未解锁'
            : canIncreaseTalent(node) ? '可点亮'
              : '不可用'
    const requires = talentRequiresLabel(node)
    const icon = node.iconUrl
      ? `<span class="tooltip-icon"><img src="${escapeHtml(node.iconUrl)}" alt=""></span>`
      : `<span class="tooltip-icon tooltip-icon-initial">${escapeHtml(String(node.name || '?').slice(0, 1))}</span>`
    const notes = []
    if (locked && parentNames) notes.push(`<div class="tooltip-note warning">需要 ${escapeHtml(parentNames)}</div>`)
    if (gated) notes.push(`<div class="tooltip-note warning">需要先在 ${escapeHtml(section.title || section.titleEn || talentTreeKey(node))} 投入 ${escapeHtml(requirement)} 点（当前计入 ${escapeHtml(availablePoints)} 点）</div>`)
    if (capped) notes.push(`<div class="tooltip-note cap">本树最多投入 ${escapeHtml(pointCap)} 点。</div>`)
    if (choices) notes.push(`<div class="tooltip-note choice">选择节点：${escapeHtml(choices)}</div>`)
    const unlockGuide = locked || gated || capped ? talentTooltipUnlockGuideHtml(node) : ''
    const rankLine = maxRank > 1 || rank > 0 || capped
      ? `<div class="tooltip-rank-line">等级 ${escapeHtml(rank)}/${escapeHtml(maxRank)}</div>`
      : ''
    const statusLine = status && !learned
      ? `<div class="tooltip-status-line">${escapeHtml(status)}</div>`
      : ''
    return `${icon}
      <div class="tooltip-title">${escapeHtml(node.name)}</div>
      <div class="tooltip-topline">
        <span>天赋</span>
        ${rankLine}
      </div>
      <div class="tooltip-topline">
        <span>瞬发</span>
      </div>
      <div class="tooltip-requires">需要 ${escapeHtml(requires)}</div>
      <p class="tooltip-description">${escapeHtml(node.description || '暂未同步法术说明。')}</p>
      ${statusLine}
      ${notes.join('')}
      ${unlockGuide}`
  }

  function showTalentTooltip(node, event) {
    const tooltip = talentTooltip()
    if (!tooltip) return
    if (state.activeChoiceNodeId && state.activeChoiceNodeId !== node.id) hideChoicePicker()
    if (state.activeChoiceNodeId === node.id && isChoicePickerVisible()) return
    tooltip.innerHTML = talentTooltipHtml(node)
    tooltip.classList.toggle('locked', !parentsSatisfied(node) || !pointRequirementSatisfied(node))
    tooltip.classList.toggle('selected', rankFor(node) > 0)
    tooltip.classList.toggle('capped', pointCapReached(node) && rankFor(node) < maxRankFor(node))
    tooltip.classList.toggle('choice', Boolean(node.choiceGroup))
    tooltip.setAttribute('aria-hidden', 'false')
    tooltip.classList.add('visible')
    setTalentHoverState(node, true)
    moveTalentTooltip(event)
  }

  function updateTalentTooltip(node, event) {
    const tooltip = talentTooltip()
    if (!tooltip || !tooltip.classList.contains('visible')) {
      showTalentTooltip(node, event)
      return
    }
    moveTalentTooltip(event)
  }

  function moveTalentTooltip(event) {
    const tooltip = talentTooltip()
    if (!tooltip || !event) return
    const viewportWidth = Math.max(0, root.innerWidth || (root.document && root.document.documentElement.clientWidth) || 0)
    const viewportHeight = Math.max(0, root.innerHeight || (root.document && root.document.documentElement.clientHeight) || 0)
    const margin = 10
    const gap = 22
    const iconWidth = 54
    const rect = tooltip.getBoundingClientRect ? tooltip.getBoundingClientRect() : { width: 320, height: 180 }
    const width = Math.max(220, rect.width || 320)
    const height = Math.max(120, rect.height || 180)
    const clientX = Number(event.clientX || 0)
    const clientY = Number(event.clientY || 0)
    const flipX = viewportWidth > 0 && clientX + gap + width + margin > viewportWidth
    let left = clientX + (flipX ? -width - gap : gap)
    let top = clientY - height - gap
    const flipY = top < margin
    if (flipY) top = clientY + gap
    if (viewportWidth > 0) {
      const minLeft = flipX ? margin : margin + iconWidth
      const maxLeft = viewportWidth - width - (flipX ? iconWidth : margin)
      left = Math.max(minLeft, Math.min(maxLeft, left))
    }
    if (viewportHeight > 0) top = Math.max(margin, Math.min(viewportHeight - height - margin, top))
    tooltip.classList.toggle('flip-x', flipX)
    tooltip.classList.toggle('flip-y', flipY)
    tooltip.style.left = `${left}px`
    tooltip.style.top = `${top}px`
  }

  function hideTalentTooltip() {
    const tooltip = talentTooltip()
    if (!isChoicePickerVisible()) setTalentHoverState(null, false)
    if (tooltip) {
      tooltip.classList.remove('visible', 'locked', 'selected', 'capped', 'choice', 'flip-x', 'flip-y')
      tooltip.setAttribute('aria-hidden', 'true')
    }
  }

  function hideTalentTooltipOutsideNode(event) {
    const tooltip = $('talentTooltip')
    if (!tooltip || !tooltip.classList.contains('visible')) return
    const target = event && event.target
    if (target && target.closest && target.closest('.talent-node')) return
    if (target && target.closest && target.closest('.talent-choice-picker')) return
    hideTalentTooltip()
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
      heroKey: state.heroKey,
      scenarioKey: state.scenarioKey,
      talents: $('talentInput') ? $('talentInput').value.trim() : '',
      talentState: {
        selectedNodes: selectedTalentEntries(),
        pvpTalents: pvpSelectionsForCurrentSpec().map((id, index) => {
          const option = pvpOptionById(id)
          return option ? { slot: index + 1, id, name: option.name } : null
        }).filter(Boolean),
        simcHint: buildTalentExportCode()
      },
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

  function selectorInitial(value, fallback) {
    const text = String(value || fallback || '').trim()
    if (!text) return 'W'
    const compact = text.replace(/\s+/g, '')
    return compact.slice(0, 2).toUpperCase()
  }

  function selectorPreviewHtml(iconUrl, title, subtitle, initial) {
    const icon = iconUrl
      ? `<span class="selector-card-icon"><img src="${escapeHtml(iconUrl)}" alt=""></span>`
      : `<span class="selector-card-icon selector-card-initial">${escapeHtml(selectorInitial(initial || title))}</span>`
    const subtitleHtml = subtitle ? `<small>${escapeHtml(subtitle)}</small>` : ''
    return `${icon}<span class="selector-card-copy"><strong>${escapeHtml(title || '')}</strong>${subtitleHtml}</span><span class="selector-card-chevron" aria-hidden="true"></span>`
  }

  function setSelectorPreview(id, html) {
    const target = $(id)
    if (target) target.innerHTML = html
  }

  function scenarioSubtitle(scenario) {
    if (!scenario) return ''
    const fightStyle = scenario.fightStyle || scenario.key || ''
    const fightStyleLabel = {
      Patchwerk: '木桩',
      DungeonSlice: '地下城切片',
      HecticAddCleave: '多目标顺劈'
    }[fightStyle] || fightStyle
    const targets = Number(scenario.targets || 0)
    return targets ? `${fightStyleLabel} · ${targets} 个目标` : fightStyleLabel
  }

  function selectorOptionIcon(iconUrl, title, initial) {
    return iconUrl
      ? `<span class="selector-option-icon"><img src="${escapeHtml(iconUrl)}" alt=""></span>`
      : `<span class="selector-option-icon selector-card-initial">${escapeHtml(selectorInitial(initial || title))}</span>`
  }

  function selectorOptionsFor(kind) {
    const classMeta = currentClassMeta()
    const specMeta = currentSpecMeta()
    if (kind === 'class') {
      return state.classes.map((item) => ({
        value: item.key,
        title: item.label,
        subtitle: '职业',
        iconUrl: item.iconUrl,
        initial: item.label || item.labelEn || item.key
      }))
    }
    if (kind === 'spec') {
      return (classMeta.specs || []).map((item) => ({
        value: item.key,
        title: item.label,
        subtitle: '专精',
        iconUrl: item.iconUrl || classMeta.iconUrl,
        initial: item.label || item.labelEn || item.key
      }))
    }
    if (kind === 'hero') {
      return currentHeroTrees().map((item) => ({
        value: item.key,
        title: item.label,
        subtitle: '英雄天赋树',
        iconUrl: specMeta.iconUrl || classMeta.iconUrl,
        initial: item.key
      }))
    }
    if (kind === 'scenario') {
      return state.scenarios.map((item) => ({
        value: item.key,
        title: item.title,
        subtitle: scenarioSubtitle(item),
        iconUrl: '',
        initial: item.key
      }))
    }
    return []
  }

  function selectedValueForSelector(kind) {
    if (kind === 'class') return state.classKey
    if (kind === 'spec') return state.specKey
    if (kind === 'hero') return state.heroKey
    if (kind === 'scenario') return state.scenarioKey
    return ''
  }

  function selectorOptionHtml(kind, option, selected) {
    const subtitleHtml = option.subtitle ? `<small>${escapeHtml(option.subtitle)}</small>` : ''
    const searchText = [option.title, option.subtitle, option.value, option.initial].filter(Boolean).join(' ')
    return `<button class="selector-option ${selected ? 'selected' : ''}" type="button" role="option" aria-selected="${selected ? 'true' : 'false'}" data-selector-kind="${escapeHtml(kind)}" data-value="${escapeHtml(option.value)}" data-search="${escapeHtml(searchText)}">
      ${selectorOptionIcon(option.iconUrl, option.title, option.initial)}
      <span class="selector-option-copy"><strong>${escapeHtml(option.title || option.value)}</strong>${subtitleHtml}</span>
      <span class="selector-option-mark" aria-hidden="true"></span>
    </button>`
  }

  function renderSelectorMenu(kind) {
    const config = selectorConfigs[kind]
    const menu = config && $(config.menuId)
    if (!menu) return
    const selected = selectedValueForSelector(kind)
    menu.innerHTML = selectorOptionsFor(kind).map((option) =>
      selectorOptionHtml(kind, option, option.value === selected)
    ).join('')
    const card = root.document && root.document.querySelector(`[data-selector-card="${kind}"]`)
    menu.hidden = !(card && card.classList.contains('open'))
  }

  function renderSelectorMenus() {
    Object.keys(selectorConfigs).forEach((kind) => renderSelectorMenu(kind))
  }

  function setSelectorOpen(kind, open) {
    const config = selectorConfigs[kind]
    if (!config || !root.document) return
    const card = root.document.querySelector(`[data-selector-card="${kind}"]`)
    const button = $(config.previewId)
    const menu = $(config.menuId)
    if (!card || !button || !menu) return
    card.classList.toggle('open', Boolean(open))
    button.setAttribute('aria-expanded', open ? 'true' : 'false')
    menu.hidden = !open
    if (open) {
      const selected = menu.querySelector('.selector-option.selected')
      if (selected && selected.scrollIntoView) selected.scrollIntoView({ block: 'nearest' })
    }
  }

  function closeSelectorMenus(exceptKind) {
    Object.keys(selectorConfigs).forEach((kind) => {
      if (kind !== exceptKind) setSelectorOpen(kind, false)
    })
  }

  function focusSelectorPreview(kind) {
    const config = selectorConfigs[kind]
    const button = config && $(config.previewId)
    if (button && button.focus) {
      button.focus()
      return true
    }
    return false
  }

  function toggleSelectorMenu(kind) {
    const config = selectorConfigs[kind]
    const menu = config && $(config.menuId)
    if (!menu) return
    const isOpen = !menu.hidden
    closeSelectorMenus(kind)
    setSelectorOpen(kind, !isOpen)
  }

  function dispatchSelectChange(select) {
    if (!select) return
    if (typeof root.Event === 'function') {
      select.dispatchEvent(new root.Event('change', { bubbles: true }))
      return
    }
    const event = root.document.createEvent('Event')
    event.initEvent('change', true, true)
    select.dispatchEvent(event)
  }

  function selectSelectorOption(kind, value) {
    const config = selectorConfigs[kind]
    const select = config && $(config.selectId)
    if (!select) return
    closeSelectorMenus()
    focusSelectorPreview(kind)
    if (select.value === value) return
    select.value = value
    dispatchSelectChange(select)
  }

  function focusSelectorOption(kind, direction) {
    const config = selectorConfigs[kind]
    const menu = config && $(config.menuId)
    if (!menu || menu.hidden) return
    const options = Array.from(menu.querySelectorAll('.selector-option'))
    if (!options.length) return
    const activeIndex = options.indexOf(root.document.activeElement)
    const selectedIndex = options.findIndex((item) => item.classList.contains('selected'))
    const baseIndex = activeIndex >= 0 ? activeIndex : Math.max(0, selectedIndex)
    const nextIndex = Math.max(0, Math.min(options.length - 1, baseIndex + direction))
    options[nextIndex].focus()
  }

  function focusSelectorEdge(kind, edge) {
    const config = selectorConfigs[kind]
    const menu = config && $(config.menuId)
    if (!menu || menu.hidden) return
    const options = Array.from(menu.querySelectorAll('.selector-option'))
    const target = edge === 'end' ? options[options.length - 1] : options[0]
    if (target) target.focus()
  }

  function focusSelectorMatch(kind, query) {
    const config = selectorConfigs[kind]
    const menu = config && $(config.menuId)
    const needle = String(query || '').trim().toLowerCase()
    if (!menu || menu.hidden || !needle) return false
    const options = Array.from(menu.querySelectorAll('.selector-option'))
    const activeIndex = Math.max(0, options.indexOf(root.document.activeElement))
    const ordered = options.slice(activeIndex + 1).concat(options.slice(0, activeIndex + 1))
    const target = ordered.find((option) => {
      const haystack = `${option.dataset.search || ''} ${option.textContent || ''}`.toLowerCase()
      return haystack.split(/\s+/).some((token) => token.startsWith(needle))
    })
    if (!target) return false
    target.focus()
    return true
  }

  function renderSelectors() {
    const classSelect = $('classSelect')
    const specSelect = $('specSelect')
    const heroSelect = $('heroSelect')
    const scenarioSelect = $('scenarioSelect')
    if (!classSelect || !specSelect || !heroSelect || !scenarioSelect) return
    classSelect.innerHTML = state.classes.map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)}</option>`
    ).join('')
    classSelect.value = state.classKey
    const klass = classByKey(state.classKey)
    specSelect.innerHTML = (klass.specs || []).map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)}</option>`
    ).join('')
    specSelect.value = state.specKey
    ensureHeroSelection()
    heroSelect.innerHTML = currentHeroTrees().map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)}</option>`
    ).join('')
    heroSelect.value = state.heroKey
    scenarioSelect.innerHTML = state.scenarios.map((item) =>
      `<option value="${escapeHtml(item.key)}">${escapeHtml(item.title)}</option>`
    ).join('')
    scenarioSelect.value = state.scenarioKey
    const classMeta = currentClassMeta()
    const specMeta = currentSpecMeta()
    const heroMeta = currentHeroMeta()
    const scenarioMeta = currentScenarioMeta()
    setSelectorPreview('classSelectPreview', selectorPreviewHtml(classMeta.iconUrl, classMeta.label || state.classKey, '职业', classMeta.label || classMeta.labelEn || classMeta.key))
    setSelectorPreview('specSelectPreview', selectorPreviewHtml(specMeta.iconUrl || classMeta.iconUrl, specMeta.label || state.specKey, '专精', specMeta.label || specMeta.labelEn || specMeta.key))
    setSelectorPreview('heroSelectPreview', selectorPreviewHtml(specMeta.iconUrl || classMeta.iconUrl, heroMeta.label || state.heroKey || '英雄天赋', '英雄天赋树', heroMeta.key || state.heroKey))
    setSelectorPreview('scenarioSelectPreview', selectorPreviewHtml('', scenarioMeta.title || state.scenarioKey, scenarioSubtitle(scenarioMeta), scenarioMeta.key || state.scenarioKey))
    const heading = $('talentPanelHeading')
    const eyebrow = $('talentPanelEyebrow')
    if (heading) heading.textContent = talentPageTitle()
    if (eyebrow) eyebrow.textContent = talentPageEyebrow()
    syncTalentDocumentTitle()
    renderSelectorMenus()
    const label = $('characterLabel')
    if (label) label.textContent = selectedSpecLabel()
  }

  function talentFooterMenuItems(scope) {
    const rootScope = scope || root.document
    const menu = rootScope && rootScope.querySelector('.talent-footer-menu')
    if (!menu || menu.hidden) return []
    return Array.from(menu.querySelectorAll('button'))
      .filter((button) => !button.disabled && button.getAttribute('aria-disabled') !== 'true')
  }

  function focusTalentFooterMenuItem(scope, target = 'first') {
    const items = talentFooterMenuItems(scope)
    if (!items.length) return false
    const activeIndex = items.indexOf(root.document && root.document.activeElement)
    const index = target === 'last' ? items.length - 1
      : typeof target === 'number' ? Math.max(0, Math.min(items.length - 1, target))
        : activeIndex >= 0 ? activeIndex : 0
    const item = items[index]
    if (item && item.focus) item.focus()
    return Boolean(item)
  }

  function stepTalentFooterMenuFocus(scope, direction) {
    const items = talentFooterMenuItems(scope)
    if (!items.length) return false
    const activeIndex = items.indexOf(root.document && root.document.activeElement)
    const baseIndex = activeIndex >= 0 ? activeIndex : (direction > 0 ? -1 : 0)
    const nextIndex = (baseIndex + direction + items.length) % items.length
    if (items[nextIndex] && items[nextIndex].focus) items[nextIndex].focus()
    return true
  }

  function closeTalentFooterMenu(scope, restoreFocus = false) {
    const rootScope = scope || root.document
    if (!rootScope) return
    const menu = rootScope.querySelector('.talent-footer-menu')
    const button = rootScope.querySelector('[data-talent-footer-menu]')
    if (menu) menu.hidden = true
    menu?.querySelector('.talent-footer-panel')?.remove()
    menu?.querySelectorAll('[data-talent-footer-panel].active').forEach((item) => item.classList.remove('active'))
    state.footerMenuPanel = ''
    if (button) {
      button.classList.remove('open')
      button.setAttribute('aria-expanded', 'false')
      if (restoreFocus && button.focus) button.focus()
    }
  }

  function toggleTalentFooterMenu(scope, focusMenu = false) {
    const rootScope = scope || root.document
    if (!rootScope) return
    const menu = rootScope.querySelector('.talent-footer-menu')
    const button = rootScope.querySelector('[data-talent-footer-menu]')
    if (!menu || !button) return
    const open = menu.hidden
    menu.hidden = !open
    button.classList.toggle('open', open)
    button.setAttribute('aria-expanded', String(open))
    if (!open) {
      state.footerMenuPanel = ''
      menu.querySelector('.talent-footer-panel')?.remove()
      menu.querySelectorAll('[data-talent-footer-panel].active').forEach((item) => item.classList.remove('active'))
    }
    if (open && focusMenu) focusTalentFooterMenuItem(rootScope, 'first')
  }

  function revealTalentFooterMenu() {
    const menu = root.document && root.document.querySelector('.talent-footer-menu')
    const button = root.document && root.document.querySelector('[data-talent-footer-menu]')
    if (menu) menu.hidden = false
    if (button) {
      button.classList.add('open')
      button.setAttribute('aria-expanded', 'true')
    }
  }

  function focusTalentFooterPanelInitial() {
    const panel = root.document && root.document.querySelector('.talent-footer-panel')
    const target = panel && panel.querySelector('textarea, input, .talent-footer-panel-primary, .talent-footer-panel-close')
    if (target && target.focus) target.focus()
  }

  function openTalentFooterPanel(panel, focusPanel = false) {
    if (!panel) return
    if (panel === 'import' && !state.footerImportDraft) {
      state.footerImportDraft = $('talentInput') ? $('talentInput').value || '' : ''
    }
    state.footerMenuPanel = panel
    renderTalents()
    revealTalentFooterMenu()
    if (focusPanel) focusTalentFooterPanelInitial()
  }

  function handleTalentFooterMenuButtonKeydown(event, scope) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      event.stopPropagation()
      toggleTalentFooterMenu(scope, true)
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      event.stopPropagation()
      const rootScope = scope || root.document
      const menu = rootScope && rootScope.querySelector('.talent-footer-menu')
      if (menu && menu.hidden) toggleTalentFooterMenu(rootScope, false)
      focusTalentFooterMenuItem(rootScope, event.key === 'ArrowUp' ? 'last' : 'first')
    } else if (event.key === 'Escape') {
      event.preventDefault()
      closeTalentFooterMenu(scope)
    }
  }

  function handleTalentFooterMenuKeydown(event, scope) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      closeTalentFooterMenu(scope, true)
      return
    }
    if (isEditableShortcutTarget(event.target)) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault()
      stepTalentFooterMenuFocus(scope, 1)
    } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault()
      stepTalentFooterMenuFocus(scope, -1)
    } else if (event.key === 'Home') {
      event.preventDefault()
      focusTalentFooterMenuItem(scope, 'first')
    } else if (event.key === 'End') {
      event.preventDefault()
      focusTalentFooterMenuItem(scope, 'last')
    }
  }

  async function runTalentFooterAction(action) {
    const closesMenu = !['copy-panel', 'copy-export', 'import-panel', 'character-panel'].includes(action)
    if (closesMenu) closeTalentFooterMenu()
    if (action === 'preset') {
      loadPresetBuild()
      syncLiveTalentRoute()
      flashTalentAction('', '已载入入门构筑')
      return
    }
    if (action === 'export') {
      exportTalentBuild()
      flashTalentAction('', '已导出到输入框')
      return
    }
    if (action === 'import') {
      const imported = await importTalentBuild()
      flashTalentAction('', imported ? '导入成功' : '导入失败', imported ? 'success' : 'error')
      return
    }
    if (action === 'share') {
      await copyTalentBuild()
      flashTalentAction('', '分享链接已复制')
      return
    }
    if (action === 'copy-panel' || action === 'copy-export') {
      await copyTalentBuild(action === 'copy-panel' ? 'share' : 'export')
      state.footerMenuPanel = action === 'copy-panel' ? 'share' : 'export'
      renderTalents()
      revealTalentFooterMenu()
      flashTalentAction('', action === 'copy-panel' ? '分享链接已复制' : '导出字符串已复制')
      return
    }
    if (action === 'import-panel') {
      const textarea = $('talentFooterImportInput')
      state.footerImportDraft = textarea ? textarea.value || '' : state.footerImportDraft
      const input = $('talentInput')
      if (input) input.value = state.footerImportDraft
      const imported = await importTalentBuild()
      state.footerMenuPanel = 'import'
      renderTalents()
      revealTalentFooterMenu()
      flashTalentAction('', imported ? '导入成功' : '导入失败', imported ? 'success' : 'error')
      return
    }
    if (action === 'character-panel') {
      state.footerMenuPanel = 'character'
      renderTalents()
      revealTalentFooterMenu()
      flashTalentAction('', '角色载入等待档案同步')
      return
    }
    if (action === 'clear') {
      const historySnapshot = talentBuildSnapshot()
      const beforeSignature = talentBuildSnapshotSignature(historySnapshot)
      resetTalentRanks()
      clearTalentAnnotations()
      setPvpSelectionsForCurrentSpec(['', '', ''])
      state.footerImportDraft = ''
      if (talentBuildSnapshotSignature() !== beforeSignature) pushTalentHistorySnapshot(historySnapshot)
      renderTalents()
      renderProfilePreview()
      syncLiveTalentRoute()
      flashTalentAction('', '已重置当前构筑')
      return
    }
  }

  function bindTalentFooterControls(scope) {
    if (!scope) return
    const menuButton = scope.querySelector('[data-talent-footer-menu]')
    if (menuButton) {
      menuButton.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        toggleTalentFooterMenu(scope)
      })
      menuButton.addEventListener('keydown', (event) => handleTalentFooterMenuButtonKeydown(event, scope))
    }
    const footerMenu = scope.querySelector('.talent-footer-menu')
    if (footerMenu) {
      footerMenu.addEventListener('keydown', (event) => handleTalentFooterMenuKeydown(event, scope))
    }
    scope.querySelectorAll('[data-talent-footer-action]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        const action = button.dataset.talentFooterAction || ''
        if (action === 'pvp') {
          closeTalentFooterMenu()
          const slotIndex = Math.max(0, Number(button.dataset.slot || 1) - 1)
          showPvpTalentPicker(slotIndex, button, event)
          return
        }
        runTalentFooterAction(action).catch((error) => {
          flashTalentAction('', '操作失败', 'error')
          showError(error)
        })
      })
      button.addEventListener('contextmenu', (event) => {
        if ((button.dataset.talentFooterAction || '') !== 'pvp') return
        event.preventDefault()
        event.stopPropagation()
        const slotIndex = Math.max(0, Number(button.dataset.slot || 1) - 1)
        clearPvpTalent(slotIndex) || hidePvpTalentPicker()
      })
      if ((button.dataset.talentFooterAction || '') === 'pvp') {
        button.addEventListener('keydown', (event) => handlePvpSlotKeydown(event, button))
      }
    })
    scope.querySelectorAll('[data-talent-footer-panel]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        openTalentFooterPanel(button.dataset.talentFooterPanel || '', event.detail === 0)
      })
    })
    scope.querySelectorAll('[data-talent-footer-panel-close]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        const restoreMenuFocus = event.detail === 0
        state.footerMenuPanel = ''
        renderTalents()
        revealTalentFooterMenu()
        if (restoreMenuFocus) focusTalentFooterMenuItem(root.document, 'first')
      })
    })
    const footerImportInput = scope.querySelector('#talentFooterImportInput')
    if (footerImportInput) {
      footerImportInput.addEventListener('click', (event) => event.stopPropagation())
      footerImportInput.addEventListener('input', (event) => {
        state.footerImportDraft = event.target.value || ''
      })
    }
    scope.querySelectorAll('#talentSearchInput').forEach((searchInput) => {
      searchInput.addEventListener('input', (event) => {
        state.talentSearchTerm = event.target.value || ''
        state.talentSearchFocusId = event.target.id || 'talentSearchInput'
        state.talentSearchIndex = 0
        renderTalents()
        focusTalentSearchInput(state.talentSearchFocusId)
        revealCurrentTalentSearchMatch()
      })
      searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault()
          state.talentSearchFocusId = searchInput.id || 'talentSearchInput'
          jumpTalentSearchMatch(event.shiftKey ? -1 : 1)
        } else if (event.key === 'Escape' && state.talentSearchTerm) {
          event.preventDefault()
          const focusId = searchInput.id || 'talentSearchInput'
          clearTalentSearch(focusId)
        }
      })
      searchInput.addEventListener('focus', () => {
        state.talentSearchFocusId = searchInput.id || 'talentSearchInput'
      })
      if (state.talentSearchTerm && state.talentSearchFocusId === searchInput.id && searchInput.setSelectionRange) {
        const end = String(state.talentSearchTerm).length
        searchInput.setSelectionRange(end, end)
      }
    })
    scope.querySelectorAll('[data-talent-search-clear]').forEach((searchClear) => {
      searchClear.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        clearTalentSearch()
      })
    })
    scope.querySelectorAll('[data-talent-search-step]').forEach((searchStep) => {
      searchStep.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        jumpTalentSearchMatch(Number(searchStep.dataset.talentSearchStep || 1))
      })
    })
  }

  function bindTalentViewControls(scope) {
    if (!scope) return
    scope.querySelectorAll('[data-talent-zoom]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        const action = button.dataset.talentZoom || ''
        if (action === 'out') shiftTalentZoom(-1)
        else if (action === 'in') shiftTalentZoom(1)
        else if (action === 'reset') setTalentZoom(1)
        flashTalentAction('', `缩放 ${talentZoomPercent()}`)
      })
    })
    applyTalentZoomToDom()
  }

  function renderTalents() {
    const tree = $('talentTree')
    if (!tree) return
    pruneTalentAnnotations()
    updateTalentToolbarState()
    hideChoicePicker()
    hidePvpTalentPicker()
    if (!state.talents.length) {
      tree.innerHTML = '<div class="blocked-state">天赋图标和说明仍在同步中，校验完成后会显示中文版天赋树。</div>'
      return
    }
    const groups = groupTalentsByTree(state.talents)
    const sections = orderedTreeSections((state.treeSections && state.treeSections.length ? state.treeSections : defaultTreeSections())
      .filter((section) => groups[section.key] && groups[section.key].length))
    const sectionData = sections.map((section) => {
      const nodes = (groups[section.key] || []).slice().sort((a, b) => Number(a.row || 0) - Number(b.row || 0) || Number(a.col || 0) - Number(b.col || 0))
      return {
        section,
        nodes,
        metrics: talentGridMetrics(nodes),
        treeImage: talentTreeImage(section.key)
      }
    })
    const fallbackNotice = state.talentStatus === 'fallback'
      ? '<div class="talent-source-note">当前显示 WebSim 可交互结构；官方 Blizzard / SimC 天赋详情同步完成后会替换为真实节点。</div>'
      : ''
    const buildChrome = `<div class="talent-calculator-chrome">
      ${talentChromeIconStripMarkup()}
    </div>`
    const headerBand = `<div class="talent-tree-headers">
      ${sectionData.map(({ section, nodes }) => treeHeaderMarkup(section, nodes)).join('')}
    </div>`
    const searchActive = Boolean(normalizedTalentSearchTerm())
    const searchMatches = talentSearchMatches()
    const activeSearchMatch = searchMatches[normalizeTalentSearchIndex(searchMatches)]
    const activeSearchId = activeSearchMatch ? activeSearchMatch.id : ''
    const blockedNode = activeBlockedTalentNode()
    const blockedRequiredIds = blockedNode ? missingRequiredTalentIdsFor(blockedNode) : new Set()
    const blockedUnlockContext = blockedNode ? talentBlockingContextFor(blockedNode) : null
    const blockedUnlockIds = blockedUnlockContext ? blockedUnlockContext.nodeIds : new Set()
    const blockedGuide = talentUnlockGuideMarkup(blockedNode)
    tree.innerHTML = `${fallbackNotice}<div class="talent-calculator-frame" style="--talent-zoom:${escapeHtml(normalizeTalentZoom(state.talentZoom).toFixed(2))};">${buildChrome}${talentViewControlsMarkup()}${headerBand}${blockedGuide}<div class="wowhead-talent-board">
      ${sectionData.map(({ section, nodes, metrics, treeImage }) => {
        const treeStyle = `--tree-accent:${escapeHtml(section.accent || currentAccent())};${treeImage ? `--tree-image:url('${escapeHtml(treeImage)}');` : ''}`
        return `<section class="talent-column talent-column-${escapeHtml(section.key)}" style="${treeStyle}">
          <div class="talent-canvas">
            ${heroFeatureMarkup(section)}
            <div class="talent-gates" aria-hidden="true">${talentGateMarkup(nodes, metrics)}</div>
            <svg class="talent-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${talentLineMarkup(nodes, metrics)}</svg>
            <div class="talent-choice-groups" aria-hidden="true">${talentChoiceGroupMarkup(nodes, metrics)}</div>
            <div class="talent-grid-inner" style="--talent-cols:${metrics.cols};--talent-rows:${metrics.rows};">
              ${nodes.map((node) => {
                const rank = rankFor(node)
                const maxRank = maxRankFor(node)
                const selected = rank > 0
                const locked = !parentsSatisfied(node) || !pointRequirementSatisfied(node)
                const capped = !locked && pointCapReached(node) && rank < maxRank
                const available = !selected && canIncreaseTalent(node)
                const maxed = selected && rank >= maxRank
                const recent = state.recentTalentId === node.id
                const recentToneClass = recent ? (state.recentTalentTone === 'remove' ? 'recent-remove' : 'recent-add') : ''
                const choice = node.choiceGroup || node.shape === 'choice'
                const choiceGroup = choice && node.choiceGroup ? choiceGroupNodes(node) : []
                const interactiveChoice = Boolean(node.choiceGroup && choiceGroup.length > 1)
                const choiceSpread = interactiveChoice ? choiceNodeSpread(node, choiceGroup) : { index: 0, x: 0, y: 0 }
                const choiceLabel = interactiveChoice ? choiceGroupLabel(node, choiceGroup) : ''
                const selectedChoicePeer = choice ? selectedChoicePeerFor(node) : null
                const choiceSelected = choice && selected
                const choiceAlternate = choice && selectedChoicePeer && selectedChoicePeer.id !== node.id
                const choiceState = choiceSelected ? 'selected' : (choiceAlternate ? 'alternate' : '')
                const ariaDisabled = interactiveChoice ? false : (locked || capped)
                const annotated = Boolean(state.talentAnnotations && state.talentAnnotations[node.id])
                const searchMatch = talentMatchesSearch(node)
                const searchCurrent = searchActive && activeSearchId === node.id
                const blockedAttempt = state.blockedTalentId === node.id
                const requiredMissing = blockedRequiredIds.has(node.id)
                const unlockRoute = blockedUnlockIds.has(node.id)
                const unlockReady = unlockRoute && rank > 0
                const unlockMissing = unlockRoute && rank <= 0
                const choiceData = choice && node.choiceGroup ? ` data-choice-group="${escapeHtml(node.choiceGroup)}" data-choice-state="${escapeHtml(choiceState || 'open')}"` : ''
                const nodeStyle = `grid-column:${Math.max(1, Number(node.col || 1))};grid-row:${Math.max(1, Number(node.row || 1))};--choice-offset-x:${choiceSpread.x}px;--choice-offset-y:${choiceSpread.y}px;--choice-index:${choiceSpread.index};`
                const labelSuffix = `${choiceLabel ? ` ${choiceLabel}` : ''}${choiceState ? ` ${choiceState === 'selected' ? '已选选择节点' : '可替换选择节点'}` : ''}`
                return `<button class="talent-node ${selected ? 'selected' : ''} ${available ? 'available' : ''} ${maxed ? 'maxed' : ''} ${recent ? 'recent' : ''} ${recentToneClass} ${locked ? 'locked' : ''} ${capped ? 'capped' : ''} ${choice ? 'choice' : ''} ${interactiveChoice ? 'choice-split' : ''} ${choiceSelected ? 'choice-selected' : ''} ${choiceAlternate ? 'choice-alternate' : ''} ${annotated ? 'annotated' : ''} ${blockedAttempt ? 'blocked-attempt' : ''} ${requiredMissing ? 'required-missing' : ''} ${unlockRoute ? 'unlock-route' : ''} ${unlockReady ? 'unlock-route-ready' : ''} ${unlockMissing ? 'unlock-route-missing' : ''} ${searchActive && searchMatch ? 'search-match' : ''} ${searchCurrent ? 'search-current' : ''} ${searchActive && !searchMatch ? 'search-dimmed' : ''} shape-${escapeHtml(node.shape || 'square')}" data-id="${escapeHtml(node.id)}" data-talent-id="${escapeHtml(node.id)}" data-tree-key="${escapeHtml(talentTreeKey(node))}" data-row="${escapeHtml(Math.max(1, Number(node.row || 1)))}" data-col="${escapeHtml(Math.max(1, Number(node.col || 1)))}"${choiceData} style="${nodeStyle}" aria-disabled="${ariaDisabled ? 'true' : 'false'}" aria-label="${escapeHtml(node.name)} ${rank}/${maxRank}${capped ? ' 点数上限已满' : ''}${blockedAttempt ? ' 刚才尝试被锁定' : ''}${requiredMissing ? ' 需要前置' : ''}${unlockRoute ? ' 解锁路径' : ''}${annotated ? ' 已标记' : ''}${searchActive && searchMatch ? ' 搜索匹配' : ''}${searchCurrent ? ' 当前搜索结果' : ''}${escapeHtml(labelSuffix)}">
                  ${annotated ? '<span class="talent-annotation" aria-hidden="true">!</span>' : ''}
                  ${choiceNodeBadgeMarkup(node, choiceGroup)}
                  <span class="talent-hit-target" aria-hidden="true"></span>
                  <span class="talent-icon-frame">${node.iconUrl ? `<img class="talent-icon" src="${escapeHtml(node.iconUrl)}" alt="">` : `<span class="talent-initial">${escapeHtml(String(node.name || '?').slice(0, 1))}</span>`}</span>
                  <span class="talent-rank">${rank}/${maxRank}</span>
                  <span class="talent-name">${escapeHtml(node.name)}</span>
                </button>`
              }).join('')}
            </div>
          </div>
        </section>`
      }).join('')}
    </div>${talentFooterMarkup()}</div>`
    tree.querySelectorAll('.talent-chrome-tab').forEach((button) => {
      button.addEventListener('click', () => {
        selectTalentChromeTab(button)
      })
      button.addEventListener('keydown', (event) => handleTalentChromeTabKeydown(event, button))
    })
    tree.querySelectorAll('[data-unlock-step]').forEach((button) => {
      bindTalentUnlockStepPreview(button)
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        focusTalentUnlockStep(button.dataset.targetId || '')
      })
    })
    tree.querySelectorAll('[data-unlock-step-add]').forEach((button) => {
      bindTalentUnlockStepPreview(button)
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        applyTalentUnlockStepRank(button.dataset.targetId || '')
      })
    })
    tree.querySelectorAll('[data-unlock-step-continue]').forEach((button) => {
      bindTalentUnlockStepPreview(button)
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        applyTalentUnlockStepRank(button.dataset.targetId || '')
      })
    })
    tree.querySelectorAll('[data-unlock-dismiss]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        clearBlockedTalentFeedback({ restoreFocus: true })
      })
    })
    tree.querySelectorAll('.talent-node').forEach((button) => {
      const node = state.talents.find((item) => item.id === button.dataset.id)
      if (!node) return
      const showTooltip = (event) => showTalentTooltip(node, event)
      const showTooltipFromFocus = () => {
        const rect = button.getBoundingClientRect()
        showTalentTooltip(node, { clientX: rect.right, clientY: rect.top })
      }
      button.addEventListener('click', (event) => {
        const id = button.dataset.id
        if (state.annotateMode) {
          event.preventDefault()
          const historySnapshot = talentBuildSnapshot()
          const annotated = toggleTalentAnnotation(id)
          pushTalentHistorySnapshot(historySnapshot)
          markRecentTalent(id)
          trackWebsimEvent('websim_talent_annotate', {
            classKey: state.classKey,
            specKey: state.specKey,
            talentId: id,
            annotated
          })
          renderTalents()
          restoreTalentNodeFocus(id)
          flashTalentAction('annotateTalentsButton', annotated ? '已标记' : '已取消标记')
          return
        }
        if (!event.shiftKey && node.choiceGroup && choiceGroupNodes(node).length > 1) {
          event.preventDefault()
          event.stopPropagation()
          showChoicePicker(node, event, button)
          trackWebsimEvent('websim_talent_choice_open', {
            classKey: state.classKey,
            specKey: state.specKey,
            heroKey: state.heroKey,
            talentId: id,
            choiceGroup: node.choiceGroup || ''
          })
          return
        }
        if (!event.shiftKey && !canIncreaseTalent(node) && rankFor(node) < maxRankFor(node)) {
          event.preventDefault()
          event.stopPropagation()
          setBlockedTalentFeedback(node)
          renderTalents()
          restoreTalentNodeFocus(id)
          trackWebsimEvent('websim_talent_blocked', {
            classKey: state.classKey,
            specKey: state.specKey,
            heroKey: state.heroKey,
            talentId: id,
            reason: talentDisabledReason(node)
          })
          return
        }
        const changed = applyTalentRankDelta(node, event.shiftKey ? -1 : 1, { restoreFocus: true })
        const next = rankFor(id)
        trackWebsimEvent('websim_talent_toggle', {
          classKey: state.classKey,
          specKey: state.specKey,
          talentId: id,
          rank: next,
          selected: next > 0,
          changed
        })
      })
      button.addEventListener('contextmenu', (event) => {
        event.preventDefault()
        const id = button.dataset.id
        if (state.annotateMode) {
          if (state.talentAnnotations && state.talentAnnotations[id]) {
            const historySnapshot = talentBuildSnapshot()
            delete state.talentAnnotations[id]
            pushTalentHistorySnapshot(historySnapshot)
            markRecentTalent(id)
            renderTalents()
            restoreTalentNodeFocus(id)
            flashTalentAction('annotateTalentsButton', '已取消标记')
            return
          }
          restoreTalentNodeFocus(id)
          flashTalentAction('annotateTalentsButton', '没有可移除的标记', 'error')
          return
        }
        decrementTalentNodeRank(node, true)
      })
      button.addEventListener('keydown', (event) => handleTalentNodeKeydown(event, node, button))
      button.addEventListener('pointerenter', showTooltip)
      button.addEventListener('pointermove', (event) => updateTalentTooltip(node, event))
      button.addEventListener('pointerleave', hideTalentTooltip)
      button.addEventListener('mouseover', showTooltip)
      button.addEventListener('mouseenter', showTooltip)
      button.addEventListener('mousemove', (event) => updateTalentTooltip(node, event))
      button.addEventListener('mouseleave', hideTalentTooltip)
      button.addEventListener('focus', showTooltipFromFocus)
      button.addEventListener('blur', hideTalentTooltip)
    })
    bindTalentFooterControls(tree)
    bindTalentViewControls(tree)
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
    ensureHeroSelection()
    const payload = await apiJson(`/api/websim/talents?class=${encodeURIComponent(state.classKey)}&spec=${encodeURIComponent(state.specKey)}&hero=${encodeURIComponent(state.heroKey || '')}`)
    state.currentSeason = payload.currentSeason || state.currentSeason
    state.dataStatus = payload.dataStatus || state.dataStatus
    state.heroKey = payload.heroKey || state.heroKey
    state.talents = payload.nodes || []
    state.presets = payload.presets || []
    state.treeSections = payload.treeSections || []
    state.talentStatus = payload.talentStatus || (state.dataStatus === 'verified' ? 'verified' : 'fallback')
    state.baseTalentRanks = {}
    state.starterTalentRanks = {}
    ;(state.talents || []).forEach((node) => {
      const rank = Math.max(0, Number(node.selectedRank || (node.selected ? 1 : 0)))
      if (rank) state.starterTalentRanks[node.id] = Math.min(maxRankFor(node), rank)
    })
    resetTalentRanks()
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
      payload.talents ? '' : `# websim_talents=${payload.talentState.simcHint}`,
      ...payload.gearSelection.items.map((item) => `${item.slot}=${item.name},id=${item.itemId || item.id}`)
    ].filter((line) => line !== '')
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

  function flashTalentAction(buttonId, message, tone = 'success') {
    const status = $('talentActionStatus')
    const button = $(buttonId)
    if (root.clearTimeout) {
      if (state.talentActionTimer) root.clearTimeout(state.talentActionTimer)
      if (state.talentActionButtonTimer) root.clearTimeout(state.talentActionButtonTimer)
    }
    state.talentActionTimer = 0
    state.talentActionButtonTimer = 0
    if (root.document) {
      root.document.querySelectorAll('.talent-action-button.action-flash').forEach((item) => item.classList.remove('action-flash'))
    }
    if (button) {
      button.classList.remove('action-flash')
      // Force a fresh animation frame when the same action is repeated quickly.
      void button.offsetWidth
      button.classList.add('action-flash')
    }
    if (status) {
      status.textContent = message || ''
      status.classList.toggle('error', tone === 'error')
      status.classList.toggle('visible', Boolean(message))
    }
    if (root.setTimeout) {
      state.talentActionButtonTimer = root.setTimeout(() => {
        if (button) button.classList.remove('action-flash')
      }, 520)
      state.talentActionTimer = root.setTimeout(() => {
        if (status) {
          status.textContent = ''
          status.classList.remove('visible', 'error')
        }
      }, tone === 'error' ? 2600 : 1800)
    }
  }

  function exportTalentBuild() {
    const input = $('talentInput')
    const code = buildTalentExportCode()
    if (input) input.value = code
    renderProfilePreview()
    return code
  }

  async function importTalentBuild() {
    const input = $('talentInput')
    const value = input ? String(input.value || '').trim() : ''
    const historySnapshot = talentBuildSnapshot()
    const beforeSignature = talentBuildSnapshotSignature(historySnapshot)
    if (value.startsWith('websim:')) {
      const selection = talentSelectionFromBuildCode(value)
      const nextClass = state.classes.find((item) => item.key === selection.classKey)
      if (nextClass) {
        state.classKey = nextClass.key
        const nextSpec = (nextClass.specs || []).find((item) => item.key === selection.specKey)
        state.specKey = (nextSpec && nextSpec.key) || ((nextClass.specs || [])[0] || {}).key || state.specKey
        state.heroKey = selection.heroKey || ''
        ensureHeroSelection()
        renderSelectors()
        syncTalentRoute()
        await Promise.all([loadTalents(), loadGear()])
      }
    }
    const imported = value && applyTalentExportCode(value)
    if (imported) {
      if (talentBuildSnapshotSignature() !== beforeSignature) pushTalentHistorySnapshot(historySnapshot)
      renderSelectors()
      renderTalents()
      renderProfilePreview()
      syncTalentRoute({ includeBuild: true })
    }
    return !!imported
  }

  async function copyTalentBuild(mode = 'export') {
    const code = mode === 'share' ? buildTalentShareUrl() : exportTalentBuild()
    try {
      if (root.navigator && root.navigator.clipboard) await root.navigator.clipboard.writeText(code)
    } catch (error) {
      // Clipboard access is optional; the exported code remains visible in the input.
    }
    return code
  }

  async function applyTalentRouteSelection(selection = talentSelectionFromLocation()) {
    const before = {
      classKey: state.classKey,
      specKey: state.specKey,
      heroKey: state.heroKey,
      scenarioKey: state.scenarioKey
    }
    applyInitialSelection(selection || {})
    const classChanged = state.classKey !== before.classKey || state.specKey !== before.specKey
    const heroChanged = state.heroKey !== before.heroKey
    renderSelectors()
    if (classChanged) {
      await Promise.all([loadTalents(), loadGear()])
    } else if (heroChanged) {
      await loadTalents()
    }
    if (selection && selection.buildCode) {
      const input = $('talentInput')
      if (input) input.value = selection.buildCode
      applyTalentExportCode(selection.buildCode)
      renderSelectors()
      renderTalents()
    }
    renderGateNotice()
    renderProfilePreview()
  }

  function loadPresetBuild() {
    const preset = state.presets[0]
    const historySnapshot = talentBuildSnapshot()
    const beforeSignature = talentBuildSnapshotSignature(historySnapshot)
    if (preset && preset.profile) renderProfilePreview(preset.profile)
    loadStarterTalentRanks()
    if (talentBuildSnapshotSignature() !== beforeSignature) pushTalentHistorySnapshot(historySnapshot)
    renderTalents()
    return preset
  }

  function bindEvents() {
    $('classSelect')?.addEventListener('change', async (event) => {
      state.classKey = event.target.value
      const klass = classByKey(state.classKey)
      state.specKey = ((klass.specs || [])[0] || {}).key || state.specKey
      state.heroKey = ''
      trackWebsimEvent('websim_class_change', { classKey: state.classKey, specKey: state.specKey })
      clearTalentHistory()
      renderSelectors()
      syncTalentRoute()
      await Promise.all([loadTalents(), loadGear()])
      renderProfilePreview()
    })
    $('specSelect')?.addEventListener('change', async (event) => {
      state.specKey = event.target.value
      trackWebsimEvent('websim_spec_change', { classKey: state.classKey, specKey: state.specKey })
      clearTalentHistory()
      renderSelectors()
      syncTalentRoute()
      await Promise.all([loadTalents(), loadGear()])
      renderProfilePreview()
    })
    $('heroSelect')?.addEventListener('change', async (event) => {
      state.heroKey = event.target.value
      trackWebsimEvent('websim_hero_change', { classKey: state.classKey, specKey: state.specKey, heroKey: state.heroKey })
      clearTalentHistory()
      renderSelectors()
      syncTalentRoute()
      await loadTalents()
      renderProfilePreview()
    })
    $('scenarioSelect')?.addEventListener('change', (event) => {
      state.scenarioKey = event.target.value
      renderSelectors()
      syncTalentRoute()
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
      loadPresetBuild()
      syncLiveTalentRoute()
      flashTalentAction('loadPresetButton', '已载入预设')
    })
    $('showTalentNamesButton')?.addEventListener('click', () => {
      state.showTalentNames = !state.showTalentNames
      updateTalentToolbarState()
      flashTalentAction('showTalentNamesButton', state.showTalentNames ? '已显示名称' : '已隐藏名称')
    })
    $('annotateTalentsButton')?.addEventListener('click', () => {
      state.annotateMode = !state.annotateMode
      updateTalentToolbarState()
      flashTalentAction('annotateTalentsButton', state.annotateMode ? '已开启标记模式' : '已退出标记模式')
    })
    $('talentHelpButton')?.addEventListener('click', (event) => {
      event.stopPropagation()
      setTalentHelpOpen(!state.talentHelpOpen)
      flashTalentAction('talentHelpButton', state.talentHelpOpen ? '帮助已打开' : '帮助已关闭')
    })
    $('resetTalentsButton')?.addEventListener('click', () => {
      const historySnapshot = talentBuildSnapshot()
      const beforeSignature = talentBuildSnapshotSignature(historySnapshot)
      resetTalentRanks()
      clearTalentAnnotations()
      setPvpSelectionsForCurrentSpec(['', '', ''])
      if (talentBuildSnapshotSignature() !== beforeSignature) pushTalentHistorySnapshot(historySnapshot)
      renderTalents()
      renderProfilePreview()
      syncLiveTalentRoute()
      flashTalentAction('resetTalentsButton', '已重置')
    })
    $('importTalentsButton')?.addEventListener('click', () => importTalentBuild()
      .then((imported) => flashTalentAction('importTalentsButton', imported ? '导入成功' : '导入失败', imported ? 'success' : 'error'))
      .catch((error) => {
        flashTalentAction('importTalentsButton', '导入失败', 'error')
        showError(error)
      }))
    $('exportTalentsButton')?.addEventListener('click', () => {
      exportTalentBuild()
      flashTalentAction('exportTalentsButton', '已导出到输入框')
    })
    $('copyTalentsButton')?.addEventListener('click', () => copyTalentBuild('share')
      .then(() => flashTalentAction('copyTalentsButton', '链接已复制'))
      .catch((error) => {
        flashTalentAction('copyTalentsButton', '复制链接失败', 'error')
        showError(error)
      }))
    root.document.querySelectorAll('[data-selector-button]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation()
        toggleSelectorMenu(button.dataset.selectorButton || '')
      })
      button.addEventListener('keydown', (event) => {
        const kind = button.dataset.selectorButton || ''
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          toggleSelectorMenu(kind)
        } else if (event.key === 'ArrowDown') {
          event.preventDefault()
          setSelectorOpen(kind, true)
          focusSelectorOption(kind, 0)
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault()
          setSelectorOpen(kind, true)
          focusSelectorEdge(kind, event.key === 'End' ? 'end' : 'start')
        } else if (event.key === 'Escape') {
          setSelectorOpen(kind, false)
        }
      })
    })
    root.document.querySelectorAll('.selector-menu').forEach((menu) => {
      menu.addEventListener('click', (event) => {
        const option = event.target.closest('.selector-option')
        if (!option) return
        event.stopPropagation()
        selectSelectorOption(option.dataset.selectorKind || '', option.dataset.value || '')
      })
      menu.addEventListener('keydown', (event) => {
        const option = event.target.closest('.selector-option')
        const kind = option ? option.dataset.selectorKind || '' : ''
        if (!option && event.key !== 'Escape') return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          selectSelectorOption(kind, option.dataset.value || '')
        } else if (event.key === 'ArrowDown') {
          event.preventDefault()
          focusSelectorOption(kind, 1)
        } else if (event.key === 'ArrowUp') {
          event.preventDefault()
          focusSelectorOption(kind, -1)
        } else if (event.key === 'Home') {
          event.preventDefault()
          focusSelectorEdge(kind, 'start')
        } else if (event.key === 'End') {
          event.preventDefault()
          focusSelectorEdge(kind, 'end')
        } else if (event.key === 'Escape') {
          event.preventDefault()
          closeSelectorMenus()
          focusSelectorPreview(kind)
        } else if (event.key && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          focusSelectorMatch(kind, event.key)
        }
      })
    })
    root.document.addEventListener('click', (event) => {
      if (!event.target.closest('.selector-card')) closeSelectorMenus()
      if (!event.target.closest('.talent-actions')) setTalentHelpOpen(false)
      if (!event.target.closest('.talent-footer-export-menu')) closeTalentFooterMenu()
      hideChoicePickerOutside(event)
      hidePvpTalentPickerOutside(event)
    })
    root.document.addEventListener('keydown', (event) => {
      if (handleTalentHistoryShortcut(event)) return
      if (event.key === 'Escape') {
        clearBlockedTalentFeedback({ restoreFocus: true })
        hideChoicePicker()
        hidePvpTalentPicker()
        closeTalentFooterMenu()
        setTalentHelpOpen(false)
      }
    })
    if (root.addEventListener) {
      root.addEventListener('popstate', () => applyTalentRouteSelection().catch(showError))
    }
    root.document.addEventListener('pointermove', hideTalentTooltipOutsideNode)
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
      const routeSelection = talentSelectionFromLocation()
      applyInitialSelection({ ...(bootstrap.defaultSelection || {}), ...routeSelection })
      state.scenarioKey = (state.scenarios[0] && state.scenarios[0].key) || state.scenarioKey
      if (routeSelection.scenarioKey) applyInitialSelection(routeSelection)
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
      if (routeSelection.buildCode) {
        const input = $('talentInput')
        if (input) input.value = routeSelection.buildCode
        applyTalentExportCode(routeSelection.buildCode)
        renderSelectors()
        renderTalents()
      }
      syncTalentRoute({ replace: true })
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
    addGearItem,
    groupTalentsByTree,
    buildTalentExportCode,
    applyTalentExportCode,
    encodePvpBuildSelections,
    decodePvpBuildSelections
  }

  if (typeof module !== 'undefined') module.exports = publicApi
  root.WebSimApp = publicApi
  init()
})(typeof window !== 'undefined' ? window : globalThis)
