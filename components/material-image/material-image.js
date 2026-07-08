function normalizeFit(value) {
  const fit = String(value || '').trim()
  if (fit === 'contain') return 'contain'
  if (fit === 'stretch') return 'stretch'
  if (fit === 'widthFix') return 'widthFix'
  return 'cover'
}

function normalizeTone(value) {
  const tone = String(value || '').trim()
  if (tone === 'border') return 'border'
  if (tone === 'socket') return 'socket'
  if (tone === 'state') return 'state'
  if (tone === 'decorative') return 'decorative'
  return 'panel'
}

function modeForFit(fit) {
  if (fit === 'contain') return 'aspectFit'
  if (fit === 'stretch') return 'scaleToFill'
  if (fit === 'widthFix') return 'widthFix'
  return 'aspectFill'
}

function clampOpacity(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 1
  return Math.max(0, Math.min(1, numeric))
}

function buildRootClass(data) {
  const classes = [
    `fit-${normalizeFit(data.fit)}`,
    `tone-${normalizeTone(data.tone)}`
  ]
  if (data.decorative) classes.push('is-decorative')
  if (data.clip) classes.push('is-clipped')
  if (!data.src) classes.push('is-empty')
  return classes.join(' ')
}

function buildRootStyle(data) {
  return `--wow-material-opacity: ${clampOpacity(data.opacity)};`
}

Component({
  options: {
    multipleSlots: true
  },
  externalClasses: ['ext-class'],
  properties: {
    src: {
      type: String,
      value: ''
    },
    fit: {
      type: String,
      value: 'cover'
    },
    tone: {
      type: String,
      value: 'panel'
    },
    opacity: {
      type: Number,
      value: 1
    },
    clip: {
      type: Boolean,
      value: true
    },
    decorative: {
      type: Boolean,
      value: false
    },
    lazyLoad: {
      type: Boolean,
      value: true
    },
    ariaLabel: {
      type: String,
      value: ''
    }
  },
  data: {
    rootClass: '',
    rootStyle: '',
    imageMode: 'aspectFill',
    failed: false
  },
  observers: {
    'src, fit, tone, opacity, clip, decorative': function updateMaterial() {
      const fit = normalizeFit(this.data.fit)
      this.setData({
        rootClass: buildRootClass(this.data),
        rootStyle: buildRootStyle(this.data),
        imageMode: modeForFit(fit),
        failed: false
      })
    }
  },
  lifetimes: {
    attached() {
      const fit = normalizeFit(this.data.fit)
      this.setData({
        rootClass: buildRootClass(this.data),
        rootStyle: buildRootStyle(this.data),
        imageMode: modeForFit(fit)
      })
    }
  },
  methods: {
    handleLoad(event) {
      this.triggerEvent('materialload', event.detail || {})
    },
    handleError(event) {
      this.setData({ failed: true })
      this.triggerEvent('materialerror', event.detail || {})
    }
  }
})
