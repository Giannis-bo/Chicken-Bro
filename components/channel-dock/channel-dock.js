Component({
  properties: {
    items: {
      type: Array,
      value: []
    },
    deferredVisualsReady: {
      type: Boolean,
      value: false
    }
  },
  methods: {
    handleTabTap(event) {
      const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
      this.triggerEvent('tabtap', {
        type: dataset.type || 'metric',
        key: dataset.key || 'today',
        value: dataset.value || ''
      })
    }
  }
})
