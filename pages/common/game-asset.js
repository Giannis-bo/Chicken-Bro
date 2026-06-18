const RENDER_ICON_56_BASE = 'https://render.worldofwarcraft.com/us/icons/56/'

function cleanIconName(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9_]+/g, '') || 'inv_misc_questionmark'
}

function uniqueList(values) {
  const seen = {}
  const result = []
  ;(values || []).forEach((value) => {
    const text = String(value || '').trim()
    if (!text || seen[text]) return
    seen[text] = true
    result.push(text)
  })
  return result
}

function fallbackTextFor(value, fallback) {
  const text = String(value || '').trim()
  if (!text) return fallback || '?'
  if (/^[A-Za-z]{2,}$/.test(text)) return text.slice(0, 2).toUpperCase()
  return text.slice(0, 1).toUpperCase()
}

function normalizeSource(value) {
  const text = String(value || '').trim()
  if (!text) return 'unknown'
  if (/battle\.net|blizzard/i.test(text)) return 'blizzard'
  return text.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '') || 'unknown'
}

function assetId(entityType, entityId, contextKey) {
  return `${entityType || 'unknown'}:${entityId || 'unknown'}:${contextKey || 'default'}`
}

function iconUrlFromIconName(iconName) {
  return `${RENDER_ICON_56_BASE}${cleanIconName(iconName)}.jpg`
}

function gameAssetFromIconUrl(options) {
  const opts = options || {}
  const entityType = String(opts.entityType || 'unknown')
  const entityId = String(opts.entityId || 'unknown')
  const contextKey = String(opts.contextKey || 'default')
  const iconUrl = String(opts.iconUrl || '')
  return {
    id: opts.id || assetId(entityType, entityId, contextKey),
    entityType,
    entityId,
    contextKey,
    assetType: opts.assetType || 'icon',
    iconUrl,
    resolutionTier: opts.resolutionTier || 'icon_56',
    source: normalizeSource(opts.source || 'unknown'),
    status: iconUrl ? (opts.status || 'fallback') : 'missing',
    semanticTags: uniqueList(opts.semanticTags || []),
    usage: uniqueList(opts.usage || []),
    fallbackText: String(opts.fallbackText || fallbackTextFor(opts.displayName || entityId)).slice(0, 12)
  }
}

function gameAssetFromIconName(options) {
  const opts = options || {}
  return gameAssetFromIconUrl({
    ...opts,
    iconUrl: opts.iconUrl || iconUrlFromIconName(opts.iconName)
  })
}

function normalizeGameAsset(gameAsset, fallbackOptions) {
  const fallback = fallbackOptions && fallbackOptions.iconName
    ? gameAssetFromIconName(fallbackOptions)
    : gameAssetFromIconUrl(fallbackOptions || {})
  if (!gameAsset || typeof gameAsset !== 'object') return fallback
  const normalized = {
    ...fallback,
    ...gameAsset
  }
  normalized.source = normalizeSource(normalized.source)
  normalized.semanticTags = uniqueList(normalized.semanticTags || fallback.semanticTags)
  normalized.usage = uniqueList(normalized.usage || fallback.usage)
  normalized.resolutionTier = normalized.resolutionTier || 'icon_56'
  normalized.status = normalized.iconUrl ? (normalized.status || fallback.status || 'fallback') : 'missing'
  normalized.fallbackText = normalized.fallbackText || fallback.fallbackText || '?'
  normalized.id = normalized.id || assetId(normalized.entityType, normalized.entityId, normalized.contextKey)
  return normalized
}

function attachGameAsset(item, fallbackOptions) {
  const source = item && typeof item === 'object' ? item : {}
  const gameAsset = normalizeGameAsset(source.gameAsset, {
    ...fallbackOptions,
    iconUrl: (fallbackOptions && fallbackOptions.iconUrl) || source.iconUrl || source.icon_url || '',
    fallbackText: (fallbackOptions && fallbackOptions.fallbackText) || source.fallbackText || source.displayName || source.name || '?'
  })
  return {
    ...source,
    iconUrl: gameAsset.iconUrl,
    fallbackText: gameAsset.fallbackText,
    gameAsset
  }
}

module.exports = {
  attachGameAsset,
  fallbackTextFor,
  gameAssetFromIconName,
  gameAssetFromIconUrl,
  iconUrlFromIconName,
  normalizeGameAsset
}
