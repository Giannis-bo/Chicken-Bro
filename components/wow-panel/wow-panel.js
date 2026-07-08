function normalizeVariant(value) {
  const variant = String(value || '').trim()
  if (variant === 'danger') return 'danger'
  if (variant === 'source_reference' || variant === 'source') return 'source'
  if (variant === 'flat') return 'flat'
  return 'default'
}

function normalizeDensity(value) {
  return String(value || '').trim() === 'dense' ? 'dense' : 'standard'
}

function normalizeMode(value) {
  const mode = String(value || '').trim()
  if (mode === 'aspectFill') return 'aspectFill'
  if (mode === 'widthFix') return 'widthFix'
  return 'aspectFit'
}

function buildRootClass(variant, density) {
  const classes = []
  const normalizedVariant = normalizeVariant(variant)
  const normalizedDensity = normalizeDensity(density)
  if (normalizedVariant !== 'default') classes.push(`is-${normalizedVariant}`)
  if (normalizedDensity === 'dense') classes.push('is-dense')
  return classes.join(' ')
}

Component({
  options: {
    multipleSlots: true
  },
  externalClasses: ['ext-class'],
  properties: {
    kicker: {
      type: String,
      value: ''
    },
    title: {
      type: String,
      value: ''
    },
    meta: {
      type: String,
      value: ''
    },
    variant: {
      type: String,
      value: 'default'
    },
    density: {
      type: String,
      value: 'standard'
    },
    materialSrc: {
      type: String,
      value: ''
    },
    materialMode: {
      type: String,
      value: 'aspectFit'
    },
    hasHeaderSlot: {
      type: Boolean,
      value: false
    }
  },
  data: {
    rootClass: '',
    normalizedMaterialMode: 'aspectFit'
  },
  observers: {
    'variant, density, materialMode': function updatePanel() {
      this.setData({
        rootClass: buildRootClass(this.data.variant, this.data.density),
        normalizedMaterialMode: normalizeMode(this.data.materialMode)
      })
    }
  },
  lifetimes: {
    attached() {
      this.setData({
        rootClass: buildRootClass(this.data.variant, this.data.density),
        normalizedMaterialMode: normalizeMode(this.data.materialMode)
      })
    }
  }
})
