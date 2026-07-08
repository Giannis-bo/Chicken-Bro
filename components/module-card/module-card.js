const DEFAULT_SOCKET = ''

function normalizeStatus(value) {
  const status = String(value || '').trim()
  if (status === 'ready_to_simulate' || status === 'verified' || status === 'ready') return 'verified'
  if (status === 'blocked') return 'blocked'
  if (status === 'partial') return 'partial'
  if (status === 'stale') return 'stale'
  if (status === 'source_reference') return 'source_reference'
  return 'source_reference'
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    title: {
      type: String,
      value: ''
    },
    metric: {
      type: String,
      value: ''
    },
    meta: {
      type: String,
      value: ''
    },
    status: {
      type: String,
      value: 'source_reference'
    },
    statusLabel: {
      type: String,
      value: ''
    },
    statusGlyph: {
      type: String,
      value: '?'
    },
    iconSrc: {
      type: String,
      value: ''
    },
    iconText: {
      type: String,
      value: ''
    },
    socketSrc: {
      type: String,
      value: DEFAULT_SOCKET
    },
    disabled: {
      type: Boolean,
      value: false
    }
  },
  data: {
    statusClass: 'status-source_reference'
  },
  observers: {
    status(status) {
      this.setData({ statusClass: `status-${normalizeStatus(status)}` })
    }
  },
  lifetimes: {
    attached() {
      this.setData({ statusClass: `status-${normalizeStatus(this.data.status)}` })
    }
  },
  methods: {
    handleTap() {
      if (this.data.disabled) return
      this.triggerEvent('cardtap', {
        title: this.data.title,
        status: normalizeStatus(this.data.status)
      })
    }
  }
})
