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
    handleItemTap(event) {
      const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
      this.triggerEvent('itemtap', {
        id: dataset.id || ''
      })
    },
    handleActionTap() {
      this.triggerEvent('actiontap', {
        type: 'metric',
        key: 'today',
        value: ''
      })
    }
  }
})
