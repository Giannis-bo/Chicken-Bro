const {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  requestBuildsDetail,
  requestBuildsHome
} = require('./builds-api')

const fallbackPayload = fallbackBuildsHome()
const payload = fallbackPayload && Array.isArray(fallbackPayload.quickActions) ? fallbackPayload : {
  quickActions: [],
  classOptions: [],
  trustedSources: []
}
const defaultSpecId = '法师-冰霜'

function findQuery(queryKey) {
  const actions = Array.isArray(payload.quickActions) ? payload.quickActions : []
  return actions.find((item) => item.key === queryKey) || actions[0] || { key: 'talents', title: '天赋构筑', desc: '' }
}

function createSelectionState(classIndex, specIndex, queryKey) {
  const classOptions = Array.isArray(payload.classOptions) ? payload.classOptions : []
  const selectedClassIndex = classOptions.length ? Math.max(0, Math.min(Number(classIndex) || 0, classOptions.length - 1)) : 0
  const selectedClass = classOptions[selectedClassIndex] || null
  const specOptions = selectedClass && Array.isArray(selectedClass.specializations) ? selectedClass.specializations : []
  const selectedSpecIndex = specOptions.length ? Math.max(0, Math.min(Number(specIndex) || 0, specOptions.length - 1)) : 0
  const selectedSpec = specOptions[selectedSpecIndex] || null
  const detail = selectedSpec && selectedSpec.id ? fallbackBuildsDetail(selectedSpec.id) : null

  return {
    selectedClassIndex,
    selectedSpecIndex,
    selectedClass,
    specOptions,
    selectedSpec,
    selectedDetail: detail,
    activeDetail: detail ? detail.details[queryKey] : null
  }
}

function findSpecSelection(specId) {
  for (let classIndex = 0; classIndex < payload.classOptions.length; classIndex += 1) {
    const specIndex = payload.classOptions[classIndex].specializations.findIndex((item) => item.id === specId)
    if (specIndex >= 0) {
      return { classIndex, specIndex }
    }
  }
  return { classIndex: 0, specIndex: 0 }
}

const defaultSelection = findSpecSelection(defaultSpecId)

Page({
  data: {
    ...payload,
    navTitle: '职业专精查询',
    activeQueryKey: 'talents',
    activeQuery: findQuery('talents'),
    ...createSelectionState(defaultSelection.classIndex, defaultSelection.specIndex, 'talents'),
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad(options) {
    const queryKey = options.query || 'talents'
    const specId = options.spec ? decodeURIComponent(options.spec) : defaultSpecId
    const selection = findSpecSelection(specId)
    const selectionState = createSelectionState(selection.classIndex, selection.specIndex, queryKey)
    this.setData({
      activeQueryKey: queryKey,
      activeQuery: findQuery(queryKey),
      ...selectionState
    })
    this.loadRemoteHome()
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
  },

  selectClass(event) {
    const classIndex = Number(event.detail.value)
    const selectionState = createSelectionState(classIndex, 0, this.data.activeQueryKey)
    this.setData(selectionState)
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
  },

  selectSpec(event) {
    const specIndex = Number(event.detail.value)
    const selectionState = createSelectionState(this.data.selectedClassIndex, specIndex, this.data.activeQueryKey)
    this.setData(selectionState)
    this.loadSelectedDetail(selectionState.selectedSpec && selectionState.selectedSpec.id)
  },

  loadRemoteHome() {
    requestBuildsHome().then(({ payload: remotePayload }) => {
      if (!remotePayload || !remotePayload.classOptions) return
      this.setData({
        quickActions: remotePayload.quickActions,
        classOptions: remotePayload.classOptions,
        trustedSources: remotePayload.trustedSources,
        lastAnalyzedAt: remotePayload.lastAnalyzedAt,
        analysisWindow: remotePayload.analysisWindow
      })
    }).catch((error) => {
      this.setData({
        requestError: error.message || String(error),
        fromFallback: true
      })
    })
  },

  loadSelectedDetail(specId) {
    if (!specId) return
    this.setData({ loading: true })
    requestBuildsDetail(specId).then(({ payload, fromFallback, error }) => {
      this.setData({
        selectedDetail: payload,
        activeDetail: payload ? payload.details[this.data.activeQueryKey] : null,
        fromFallback,
        requestError: error || ''
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})
