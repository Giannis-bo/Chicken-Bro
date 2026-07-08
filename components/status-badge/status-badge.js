const defaultBaseSrc = ''

function normalizeState(value) {
  const state = String(value || '').trim()
  if (state === 'ready_to_simulate') return 'verified'
  if (state === 'verified') return 'verified'
  if (state === 'blocked') return 'blocked'
  if (state === 'partial') return 'partial'
  if (state === 'stale') return 'stale'
  if (state === 'source_reference') return 'source_reference'
  return 'source_reference'
}

function glyphClass(value) {
  const text = String(value || '').trim()
  return text.length > 1 ? 'is-wide' : ''
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: {
      type: String,
      value: 'source_reference'
    },
    stateClass: {
      type: String,
      value: ''
    },
    label: {
      type: String,
      value: ''
    },
    glyph: {
      type: String,
      value: '?'
    },
    baseSrc: {
      type: String,
      value: defaultBaseSrc
    },
    size: {
      type: String,
      value: 'default'
    },
    showLabel: {
      type: Boolean,
      value: false
    }
  },
  data: {
    toneClass: 'status-source_reference',
    glyphClass: ''
  },
  observers: {
    'state, stateClass, glyph': function updateState(state, stateClass, glyph) {
      const toneClass = stateClass || `status-${normalizeState(state)}`
      this.setData({
        toneClass,
        glyphClass: glyphClass(glyph)
      })
    }
  },
  lifetimes: {
    attached() {
      const { state, stateClass, glyph } = this.data
      const toneClass = stateClass || `status-${normalizeState(state)}`
      this.setData({
        toneClass,
        glyphClass: glyphClass(glyph)
      })
    }
  }
})
