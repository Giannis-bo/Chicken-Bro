function normalizeEntryMode(value) {
  const mode = String(value || '').trim()
  if (mode === 'workbench_context') return 'workbench_context'
  return 'tab'
}

function normalizeInputState(value, disabled, submitting) {
  if (submitting) return 'submitting'
  if (disabled) return 'disabled'
  const state = String(value || '').trim()
  if (state === 'focused') return 'focused'
  return 'idle'
}

function buildRootClass(data) {
  const classes = [
    `entry-${normalizeEntryMode(data.entryMode)}`,
    `input-${normalizeInputState(data.inputState, data.inputDisabled, data.submitting)}`
  ]
  if (data.hasDrawer) classes.push('has-drawer')
  if (data.messages && data.messages.length) classes.push('has-messages')
  if (data.contextTitle || data.contextMeta) classes.push('has-context')
  return classes.join(' ')
}

function normalizeScrollAnchor(value) {
  const anchor = String(value || '').trim()
  return anchor || 'chat-bottom-a'
}

function buildInputBarStyle(data) {
  return data.safeAreaBottom ? `--chat-safe-bottom: ${data.safeAreaBottom};` : ''
}

function applyShellState(component) {
  const next = {
    rootClass: buildRootClass(component.data),
    inputBarStyle: buildInputBarStyle(component.data),
    bottomAnchorId: normalizeScrollAnchor(component.data.scrollIntoView)
  }
  const patch = {}
  Object.keys(next).forEach((key) => {
    if (component.data[key] !== next[key]) patch[key] = next[key]
  })
  if (Object.keys(patch).length) component.setData(patch)
}

Component({
  options: {
    multipleSlots: true
  },
  externalClasses: ['ext-class'],
  properties: {
    entryMode: {
      type: String,
      value: 'tab'
    },
    contextTitle: {
      type: String,
      value: ''
    },
    contextMeta: {
      type: String,
      value: ''
    },
    messages: {
      type: Array,
      value: []
    },
    topics: {
      type: Array,
      value: []
    },
    inputValue: {
      type: String,
      value: ''
    },
    inputPlaceholder: {
      type: String,
      value: '问炸鸡队长'
    },
    contextActionLabel: {
      type: String,
      value: '上下文'
    },
    newTopicLabel: {
      type: String,
      value: '新话题'
    },
    sendLabel: {
      type: String,
      value: '发送'
    },
    sendingLabel: {
      type: String,
      value: '整理中'
    },
    inputState: {
      type: String,
      value: 'idle'
    },
    inputDisabled: {
      type: Boolean,
      value: false
    },
    submitting: {
      type: Boolean,
      value: false
    },
    hasDrawer: {
      type: Boolean,
      value: false
    },
    safeAreaBottom: {
      type: String,
      value: ''
    },
    scrollIntoView: {
      type: String,
      value: ''
    }
  },
  data: {
    rootClass: '',
    inputBarStyle: '',
    bottomAnchorId: 'chat-bottom-a'
  },
  observers: {
    'entryMode, inputState, inputDisabled, submitting, hasDrawer, messages, contextTitle, contextMeta, safeAreaBottom, scrollIntoView': function updateShell() {
      applyShellState(this)
    }
  },
  lifetimes: {
    attached() {
      applyShellState(this)
    }
  },
  methods: {
    handleInput(event) {
      const value = event.detail && event.detail.value ? event.detail.value : ''
      this.triggerEvent('inputchange', { value })
    },
    handleFocus() {
      this.triggerEvent('inputfocus', {})
    },
    handleBlur() {
      this.triggerEvent('inputblur', {})
    },
    handleSend() {
      if (this.data.inputDisabled || this.data.submitting) return
      this.triggerEvent('send', { value: this.data.inputValue })
    },
    handleNewTopic() {
      this.triggerEvent('newtopic', {})
    },
    handleOpenDrawer() {
      this.triggerEvent('opendrawer', {})
    },
    handleNextQuestion(event) {
      const value = event.currentTarget && event.currentTarget.dataset
        ? event.currentTarget.dataset.value
        : ''
      this.triggerEvent('nextquestion', { value })
    }
  }
})
