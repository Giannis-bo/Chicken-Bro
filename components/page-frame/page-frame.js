function normalizeDensity(value) {
  const density = String(value || '').trim()
  if (density === 'dense') return 'dense'
  if (density === 'roomy') return 'roomy'
  return 'standard'
}

function normalizeTone(value) {
  const tone = String(value || '').trim()
  if (tone === 'flat') return 'flat'
  return 'default'
}

function cssVar(name, value) {
  const text = String(value || '').trim()
  return text ? `${name}: ${text};` : ''
}

function buildRootClass(density, tone) {
  const classes = []
  const normalizedDensity = normalizeDensity(density)
  const normalizedTone = normalizeTone(tone)
  if (normalizedDensity !== 'standard') classes.push(`is-${normalizedDensity}`)
  if (normalizedTone !== 'default') classes.push(`is-${normalizedTone}`)
  return classes.join(' ')
}

function buildContentStyle(data) {
  return [
    cssVar('--wow-page-gutter', data.gutter),
    cssVar('--wow-page-top', data.topInset),
    cssVar('--wow-page-bottom', data.bottomInset),
    cssVar('--wow-page-section-gap', data.sectionGap)
  ].filter(Boolean).join(' ')
}

Component({
  options: {
    multipleSlots: true
  },
  externalClasses: ['ext-class'],
  properties: {
    scroll: {
      type: Boolean,
      value: true
    },
    density: {
      type: String,
      value: 'standard'
    },
    tone: {
      type: String,
      value: 'default'
    },
    gutter: {
      type: String,
      value: ''
    },
    topInset: {
      type: String,
      value: ''
    },
    bottomInset: {
      type: String,
      value: ''
    },
    sectionGap: {
      type: String,
      value: ''
    },
    lowerThreshold: {
      type: Number,
      value: 80
    }
  },
  data: {
    rootClass: '',
    contentStyle: ''
  },
  observers: {
    'density, tone, gutter, topInset, bottomInset, sectionGap': function updateFrame() {
      this.setData({
        rootClass: buildRootClass(this.data.density, this.data.tone),
        contentStyle: buildContentStyle(this.data)
      })
    }
  },
  lifetimes: {
    attached() {
      this.setData({
        rootClass: buildRootClass(this.data.density, this.data.tone),
        contentStyle: buildContentStyle(this.data)
      })
    }
  },
  methods: {
    handleScrollToLower(event) {
      this.triggerEvent('scrolltolower', event.detail || {})
    }
  }
})
