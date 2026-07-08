function normalizeSurface(value) {
  const surface = String(value || '').trim()
  if (surface === 'news') return 'news'
  if (surface === 'builds') return 'builds'
  if (surface === 'workbench') return 'workbench'
  if (surface === 'talent') return 'talent'
  if (surface === 'gear') return 'gear'
  if (surface === 'simc') return 'simc'
  if (surface === 'chickenbro') return 'chickenbro'
  if (surface === 'tasks') return 'tasks'
  if (surface === 'profile') return 'profile'
  return 'default'
}

function normalizeDensity(value) {
  const density = String(value || '').trim()
  if (density === 'compact') return 'compact'
  if (density === 'large') return 'large'
  return 'standard'
}

function cssVar(name, value) {
  const text = String(value || '').trim()
  return text ? `${name}: ${text};` : ''
}

function buildRootClass(data) {
  const classes = [
    `surface-${normalizeSurface(data.surface)}`,
    `density-${normalizeDensity(data.density)}`
  ]
  if (data.tabSafe) classes.push('is-tab-safe')
  if (data.navSafe) classes.push('is-nav-safe')
  if (data.lockScroll) classes.push('is-lock-scroll')
  return classes.join(' ')
}

function buildRootStyle(data) {
  return [
    cssVar('--wow-app-top-safe', data.topSafe),
    cssVar('--wow-app-bottom-safe', data.bottomSafe),
    cssVar('--wow-app-gutter', data.gutter)
  ].filter(Boolean).join(' ')
}

Component({
  options: {
    multipleSlots: true
  },
  externalClasses: ['ext-class'],
  properties: {
    surface: {
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
      value: 'aspectFill'
    },
    tabSafe: {
      type: Boolean,
      value: true
    },
    navSafe: {
      type: Boolean,
      value: false
    },
    lockScroll: {
      type: Boolean,
      value: false
    },
    topSafe: {
      type: String,
      value: ''
    },
    bottomSafe: {
      type: String,
      value: ''
    },
    gutter: {
      type: String,
      value: ''
    }
  },
  data: {
    rootClass: '',
    rootStyle: ''
  },
  observers: {
    'surface, density, tabSafe, navSafe, lockScroll, topSafe, bottomSafe, gutter': function updateShell() {
      this.setData({
        rootClass: buildRootClass(this.data),
        rootStyle: buildRootStyle(this.data)
      })
    }
  },
  lifetimes: {
    attached() {
      this.setData({
        rootClass: buildRootClass(this.data),
        rootStyle: buildRootStyle(this.data)
      })
    }
  }
})
