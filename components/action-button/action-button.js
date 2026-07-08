function normalizeTone(value) {
  const tone = String(value || '').trim()
  if (tone === 'danger') return 'danger'
  if (tone === 'secondary') return 'secondary'
  if (tone === 'ghost') return 'ghost'
  return 'primary'
}

function normalizeSize(value) {
  const size = String(value || '').trim()
  if (size === 'compact') return 'compact'
  if (size === 'large') return 'large'
  return 'default'
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    label: {
      type: String,
      value: ''
    },
    meta: {
      type: String,
      value: ''
    },
    icon: {
      type: String,
      value: ''
    },
    tone: {
      type: String,
      value: 'primary'
    },
    size: {
      type: String,
      value: 'default'
    },
    disabled: {
      type: Boolean,
      value: false
    },
    loading: {
      type: Boolean,
      value: false
    },
    block: {
      type: Boolean,
      value: false
    }
  },
  data: {
    rootClass: 'tone-primary size-default'
  },
  observers: {
    'tone, size, disabled, loading, block': function updateClass(tone, size, disabled, loading, block) {
      const classes = [
        `tone-${normalizeTone(tone)}`,
        `size-${normalizeSize(size)}`
      ]
      if (disabled) classes.push('is-disabled')
      if (loading) classes.push('is-loading')
      if (block) classes.push('is-block')
      this.setData({ rootClass: classes.join(' ') })
    }
  },
  lifetimes: {
    attached() {
      const { tone, size, disabled, loading, block } = this.data
      const classes = [
        `tone-${normalizeTone(tone)}`,
        `size-${normalizeSize(size)}`
      ]
      if (disabled) classes.push('is-disabled')
      if (loading) classes.push('is-loading')
      if (block) classes.push('is-block')
      this.setData({ rootClass: classes.join(' ') })
    }
  },
  methods: {
    handleTap() {
      if (this.data.disabled || this.data.loading) return
      this.triggerEvent('actiontap', {
        label: this.data.label,
        tone: normalizeTone(this.data.tone)
      })
    }
  }
})
