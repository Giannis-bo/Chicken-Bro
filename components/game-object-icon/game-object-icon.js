const {
  fallbackTextFor,
  iconUrlFromIconName,
  normalizeGameAsset
} = require('../../pages/common/game-asset')
const {
  CLASS_ASSET_MAP,
  SPEC_ASSET_MAP,
  classIconUrlFor,
  specIconUrlFor
} = require('../../pages/common/wow-spec-assets')

const DEFAULT_FRAME = ''

function normalizeSize(value) {
  const size = String(value || '').trim()
  if (size === 'small') return 'small'
  if (size === 'large') return 'large'
  return 'default'
}

function normalizeShape(value) {
  const shape = String(value || '').trim()
  return shape === 'square' ? 'square' : 'circle'
}

function resolveMappedIcon(data) {
  if (data.iconSrc) return data.iconSrc
  if (data.iconName) return iconUrlFromIconName(data.iconName)
  if (data.objectType === 'class' && CLASS_ASSET_MAP[data.classKey]) return classIconUrlFor(data.classKey)
  if (data.objectType === 'spec' && SPEC_ASSET_MAP[data.specKey]) return specIconUrlFor(data.specKey, data.classKey)
  return ''
}

function buildRootClass(size, shape, status) {
  const classes = [`status-${status || 'source_reference'}`]
  const normalizedSize = normalizeSize(size)
  const normalizedShape = normalizeShape(shape)
  if (normalizedSize !== 'default') classes.push(`wow-game-object-icon-${normalizedSize}`)
  if (normalizedShape !== 'circle') classes.push(`wow-game-object-icon-${normalizedShape}`)
  return classes.join(' ')
}

function resolveIconState(data) {
  const mappedIcon = resolveMappedIcon(data)
  const fallbackText = data.fallbackText || fallbackTextFor(data.displayName || data.specKey || data.classKey || data.entityId, '?')
  const asset = normalizeGameAsset(data.gameAsset, {
    entityType: data.objectType || data.entityType || 'unknown',
    entityId: data.entityId || data.specKey || data.classKey || 'unknown',
    contextKey: data.contextKey || 'component',
    iconUrl: mappedIcon,
    fallbackText,
    displayName: data.displayName || data.entityId || data.specKey || data.classKey,
    source: data.source || 'local_mapping',
    status: mappedIcon ? (data.status || 'verified') : (data.status || 'missing')
  })
  const status = asset.iconUrl ? (asset.status || 'verified') : 'missing'
  return {
    resolvedIconSrc: asset.iconUrl || '',
    resolvedFallbackText: String(asset.fallbackText || fallbackText || '?').slice(0, 2),
    ariaLabel: data.displayName || asset.entityId || asset.fallbackText || 'game object',
    rootClass: buildRootClass(data.size, data.shape, status)
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    gameAsset: {
      type: Object,
      value: null
    },
    objectType: {
      type: String,
      value: 'unknown'
    },
    entityType: {
      type: String,
      value: ''
    },
    entityId: {
      type: String,
      value: ''
    },
    contextKey: {
      type: String,
      value: ''
    },
    classKey: {
      type: String,
      value: ''
    },
    specKey: {
      type: String,
      value: ''
    },
    displayName: {
      type: String,
      value: ''
    },
    iconSrc: {
      type: String,
      value: ''
    },
    iconName: {
      type: String,
      value: ''
    },
    fallbackText: {
      type: String,
      value: ''
    },
    source: {
      type: String,
      value: ''
    },
    status: {
      type: String,
      value: ''
    },
    size: {
      type: String,
      value: 'default'
    },
    shape: {
      type: String,
      value: 'circle'
    },
    frameSrc: {
      type: String,
      value: DEFAULT_FRAME
    },
    lazyLoad: {
      type: Boolean,
      value: true
    },
    showSourceDot: {
      type: Boolean,
      value: false
    }
  },
  data: {
    resolvedIconSrc: '',
    resolvedFallbackText: '?',
    ariaLabel: 'game object',
    rootClass: 'status-source_reference'
  },
  observers: {
    'gameAsset, objectType, entityType, entityId, contextKey, classKey, specKey, displayName, iconSrc, iconName, fallbackText, source, status, size, shape': function updateIcon() {
      this.setData(resolveIconState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(resolveIconState(this.data))
    }
  }
})
