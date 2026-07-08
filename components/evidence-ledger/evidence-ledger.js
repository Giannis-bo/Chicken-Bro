function normalizeRows(rows) {
  return Array.isArray(rows) ? rows : []
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    title: {
      type: String,
      value: '证据明细'
    },
    summary: {
      type: String,
      value: ''
    },
    expanded: {
      type: Boolean,
      value: false
    },
    rows: {
      type: Array,
      value: []
    },
    collapsedRows: {
      type: Number,
      value: 3
    }
  },
  data: {
    visibleRows: []
  },
  observers: {
    'rows, expanded, collapsedRows': function updateRows(rows, expanded, collapsedRows) {
      const normalizedRows = normalizeRows(rows)
      const limit = Math.max(1, Number(collapsedRows || 3))
      this.setData({
        visibleRows: expanded ? normalizedRows : normalizedRows.slice(0, limit)
      })
    }
  },
  lifetimes: {
    attached() {
      const normalizedRows = normalizeRows(this.data.rows)
      const limit = Math.max(1, Number(this.data.collapsedRows || 3))
      this.setData({
        visibleRows: this.data.expanded ? normalizedRows : normalizedRows.slice(0, limit)
      })
    }
  },
  methods: {
    handleToggle() {
      this.triggerEvent('toggle', {
        expanded: !this.data.expanded
      })
    },
    handleRowTap(event) {
      const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
      this.triggerEvent('rowtap', {
        key: dataset.key || '',
        status: dataset.status || ''
      })
    }
  }
})
