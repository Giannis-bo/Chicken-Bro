const GLYPH_BY_STATE = {
  ready_to_simulate: '✓',
  ready: '✓',
  verified: '✓',
  blocked: '!',
  partial: '~',
  stale: '↻',
  source_reference: 'i',
  unknown: '?',
  loading: '...',
  empty: '-',
  error: '!'
}

function normalizeState(value) {
  const state = String(value || '').trim()
  if (state === 'ready_to_simulate') return 'ready_to_simulate'
  if (state === 'ready') return 'ready_to_simulate'
  if (state === 'verified') return 'ready_to_simulate'
  if (state === 'blocked') return 'blocked'
  if (state === 'partial') return 'partial'
  if (state === 'stale') return 'stale'
  if (state === 'source_reference') return 'source_reference'
  if (state === 'loading') return 'loading'
  if (state === 'empty') return 'empty'
  if (state === 'error') return 'error'
  return 'unknown'
}

function normalizeSize(value) {
  const size = String(value || '').trim()
  if (size === 'compact') return 'compact'
  if (size === 'large') return 'large'
  if (size === 'hero') return 'hero'
  return 'default'
}

function normalizeMode(value) {
  const mode = String(value || '').trim()
  if (mode === 'atomic') return 'atomic'
  return 'layered'
}

function normalizeShape(value) {
  const shape = String(value || '').trim()
  if (shape === 'auto' || !shape) return 'auto'
  if (shape === 'triangle') return 'triangle'
  if (shape === 'circle') return 'circle'
  if (shape === 'diamond') return 'diamond'
  if (shape === 'seal') return 'seal'
  if (shape === 'pill') return 'pill'
  if (shape === 'shield') return 'auto'
  return 'auto'
}

function shapeForState(state, shape) {
  const normalizedShape = normalizeShape(shape)
  if (normalizedShape !== 'auto') return normalizedShape
  const normalizedState = normalizeState(state)
  if (normalizedState === 'blocked' || normalizedState === 'error') return 'triangle'
  if (normalizedState === 'partial' || normalizedState === 'loading') return 'diamond'
  return 'circle'
}

function glyphClass(value) {
  const text = String(value || '').trim()
  if (text.length >= 3) return 'is-long'
  if (text.length >= 2) return 'is-wide'
  return ''
}

function buildRootClass(data) {
  const state = normalizeState(data.state)
  const classes = [
    `state-${state}`,
    `size-${normalizeSize(data.size)}`,
    `mode-${normalizeMode(data.mode)}`,
    `shape-${shapeForState(data.state, data.shape)}`
  ]
  if (data.fill) classes.push('is-fill')
  if (data.showLabel) classes.push('has-label')
  if (!data.baseSrc) classes.push('has-css-base')
  return classes.join(' ')
}

function resolveGlyph(state, glyph) {
  const explicit = String(glyph || '').trim()
  if (explicit) return explicit
  return GLYPH_BY_STATE[normalizeState(state)] || '?'
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: {
      type: String,
      value: 'unknown'
    },
    label: {
      type: String,
      value: ''
    },
    glyph: {
      type: String,
      value: ''
    },
    mode: {
      type: String,
      value: 'layered'
    },
    shape: {
      type: String,
      value: 'auto'
    },
    size: {
      type: String,
      value: 'default'
    },
    baseSrc: {
      type: String,
      value: ''
    },
    atomicSrc: {
      type: String,
      value: ''
    },
    showLabel: {
      type: Boolean,
      value: false
    },
    fill: {
      type: Boolean,
      value: false
    }
  },
  data: {
    rootClass: '',
    resolvedGlyph: '?',
    glyphClass: '',
    isAtomic: false,
    atomicLoadFailed: false,
    lastAtomicSrc: ''
  },
  methods: {
    updateVisualState() {
      const resolvedGlyph = resolveGlyph(this.data.state, this.data.glyph)
      const atomicSrc = String(this.data.atomicSrc || '')
      const atomicSrcChanged = this.data.lastAtomicSrc !== atomicSrc
      const nextData = {
        rootClass: buildRootClass(this.data),
        resolvedGlyph,
        glyphClass: glyphClass(resolvedGlyph),
        isAtomic: normalizeMode(this.data.mode) === 'atomic',
        lastAtomicSrc: atomicSrc
      }
      if (atomicSrcChanged) {
        nextData.atomicLoadFailed = false
      }
      if (
        this.data.rootClass === nextData.rootClass &&
        this.data.resolvedGlyph === nextData.resolvedGlyph &&
        this.data.glyphClass === nextData.glyphClass &&
        this.data.isAtomic === nextData.isAtomic &&
        this.data.lastAtomicSrc === nextData.lastAtomicSrc &&
        (!atomicSrcChanged || this.data.atomicLoadFailed === nextData.atomicLoadFailed)
      ) {
        return
      }
      this.setData(nextData)
    },
    handleAtomicError() {
      if (this.data.atomicLoadFailed) return
      this.setData({ atomicLoadFailed: true })
    }
  },
  observers: {
    'state, label, glyph, mode, shape, size, baseSrc, atomicSrc, showLabel, fill': function updateVisual() {
      this.updateVisualState()
    }
  },
  lifetimes: {
    attached() {
      this.updateVisualState()
    }
  }
})
