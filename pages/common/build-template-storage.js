const { requestJson } = require('./api-client')

const BUILD_TEMPLATE_STORAGE_KEY = 'wow_build_templates_v1'
const BUILD_TEMPLATE_SCHEMA_VERSION = 1
const VALID_TEMPLATE_TYPES = ['talent', 'gear']

function storageGet(key) {
  if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') return ''
  return wx.getStorageSync(key) || ''
}

function storageSet(key, value) {
  if (typeof wx !== 'undefined' && typeof wx.setStorageSync === 'function') {
    wx.setStorageSync(key, value)
  }
}

function parseTemplates() {
  const stored = storageGet(BUILD_TEMPLATE_STORAGE_KEY)
  if (!stored) return []
  if (Array.isArray(stored)) return stored
  try {
    const parsed = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    return []
  }
}

function saveTemplates(templates) {
  storageSet(BUILD_TEMPLATE_STORAGE_KEY, JSON.stringify(templates || []))
}

function randomTemplateId(type) {
  return `${type || 'template'}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function normalizeString(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function templateStatusLabel(type, status) {
  if (status === 'saved') return '已保存'
  if (status === 'complete') return '完整配置'
  if (status === 'encoded') return '已编码'
  if (status === 'simc_ready') return 'SimC-ready'
  if (status === 'partial') return '缺字段'
  if (status === 'blocked') return '不可计算'
  return type === 'gear' ? '不可计算' : '待编码'
}

function normalizeTemplate(record, existing) {
  const source = record || {}
  const type = VALID_TEMPLATE_TYPES.includes(source.type) ? source.type : ''
  if (!type) return null
  const now = new Date().toISOString()
  const rawString = normalizeString(source.rawString)
  if (!rawString) return null
  const status = normalizeString(source.status) || (type === 'gear' ? 'complete' : 'saved')
  const createdAt = normalizeString(existing && existing.createdAt) || normalizeString(source.createdAt) || now
  const updatedAt = normalizeString(source.updatedAt) || now
  const className = normalizeString(source.className)
  const specName = normalizeString(source.specName)
  const scenarioTitle = normalizeString(source.scenarioTitle)
  const fallbackTitle = [specName + className, scenarioTitle].filter(Boolean).join(' · ')

  return {
    id: normalizeString(existing && existing.id) || normalizeString(source.id) || randomTemplateId(type),
    clientId: normalizeString(source.clientId),
    type,
    title: normalizeString(source.title) || fallbackTitle || (type === 'talent' ? '天赋模板' : '装备模板'),
    classKey: normalizeString(source.classKey),
    className,
    specKey: normalizeString(source.specKey),
    specName,
    heroKey: normalizeString(source.heroKey),
    heroLabel: normalizeString(source.heroLabel),
    scenarioKey: normalizeString(source.scenarioKey),
    scenarioTitle,
    rawString,
    simcLines: normalizeArray(source.simcLines),
    status,
    statusLabel: normalizeString(source.statusLabel) || templateStatusLabel(type, status),
    source: normalizeString(source.source) || (type === 'talent' ? 'WebSim 天赋模拟器' : '装备模拟器'),
    metadata: source.metadata && typeof source.metadata === 'object' ? source.metadata : {},
    createdAt,
    updatedAt,
    remote: !!source.remote,
    schemaVersion: BUILD_TEMPLATE_SCHEMA_VERSION
  }
}

function sortedTemplates(templates) {
  return (templates || []).slice(0).sort((left, right) => {
    const leftTime = new Date(left.updatedAt || left.createdAt || 0).getTime() || 0
    const rightTime = new Date(right.updatedAt || right.createdAt || 0).getTime() || 0
    return rightTime - leftTime
  })
}

function listBuildTemplates(type) {
  const templates = parseTemplates()
    .map((item) => normalizeTemplate(item, item))
    .filter(Boolean)
  const filtered = VALID_TEMPLATE_TYPES.includes(type)
    ? templates.filter((item) => item.type === type)
    : templates
  return sortedTemplates(filtered)
}

function saveBuildTemplate(record) {
  const existingTemplates = parseTemplates()
    .map((item) => normalizeTemplate(item, item))
    .filter(Boolean)
  const incomingType = record && record.type
  const incomingRaw = normalizeString(record && record.rawString)
  const existingIndex = existingTemplates.findIndex((item) => item.type === incomingType && item.rawString === incomingRaw)
  const existing = existingIndex >= 0 ? existingTemplates[existingIndex] : null
  const next = normalizeTemplate(record, existing)
  if (!next) return null
  const templates = existingIndex >= 0
    ? existingTemplates.map((item, index) => (index === existingIndex ? next : item))
    : existingTemplates.concat([next])
  saveTemplates(sortedTemplates(templates))
  return next
}

function deleteBuildTemplate(id) {
  const templateId = normalizeString(id)
  if (!templateId) return false
  const templates = parseTemplates()
    .map((item) => normalizeTemplate(item, item))
    .filter(Boolean)
  const next = templates.filter((item) => item.id !== templateId)
  saveTemplates(sortedTemplates(next))
  return next.length !== templates.length
}

function templateMatches(left, right) {
  if (!left || !right) return false
  if (left.id && right.id && left.id === right.id) return true
  if (left.id && right.clientId && left.id === right.clientId) return true
  if (left.clientId && right.id && left.clientId === right.id) return true
  return left.type === right.type && left.rawString === right.rawString
}

function remoteTemplatesFromPayload(payload) {
  const source = payload || {}
  const templates = []
  if (source.template) templates.push(source.template)
  if (Array.isArray(source.templates)) templates.push(...source.templates)
  return templates
    .map((item) => normalizeTemplate({ ...item, remote: true }, null))
    .filter(Boolean)
}

function mergeRemoteBuildTemplates(remoteTemplates) {
  const incoming = (remoteTemplates || [])
    .map((item) => normalizeTemplate({ ...item, remote: true }, null))
    .filter(Boolean)
  if (!incoming.length) return listBuildTemplates()
  const merged = listBuildTemplates()
  incoming.forEach((remoteTemplate) => {
    const existingIndex = merged.findIndex((item) => templateMatches(item, remoteTemplate))
    if (existingIndex >= 0) {
      merged[existingIndex] = {
        ...merged[existingIndex],
        ...remoteTemplate,
        id: remoteTemplate.id || merged[existingIndex].id,
        remote: true
      }
    } else {
      merged.push({ ...remoteTemplate, remote: true })
    }
  })
  saveTemplates(sortedTemplates(merged))
  return listBuildTemplates()
}

function buildTemplatesPath(type) {
  return VALID_TEMPLATE_TYPES.includes(type)
    ? `/api/me/build-templates?type=${encodeURIComponent(type)}`
    : '/api/me/build-templates'
}

function validateTemplateListPayload(data) {
  return !!(data && Array.isArray(data.templates))
}

async function fetchBuildTemplates(type) {
  const result = await requestJson(buildTemplatesPath(type), {
    auth: true,
    fallback: () => ({
      schemaVersion: BUILD_TEMPLATE_SCHEMA_VERSION,
      templates: listBuildTemplates(type)
    }),
    validate: validateTemplateListPayload
  })
  if (!result.fromFallback) {
    mergeRemoteBuildTemplates(result.payload.templates || [])
    return {
      ...result,
      payload: {
        ...result.payload,
        templates: listBuildTemplates(type)
      }
    }
  }
  return result
}

async function syncBuildTemplate(record) {
  const localTemplate = saveBuildTemplate(record)
  if (!localTemplate) {
    return {
      payload: {
        schemaVersion: BUILD_TEMPLATE_SCHEMA_VERSION,
        template: null,
        templates: listBuildTemplates()
      },
      fromFallback: true,
      error: 'invalid build template'
    }
  }
  const result = await requestJson('/api/me/build-templates', {
    method: 'POST',
    auth: true,
    data: { template: localTemplate },
    fallback: () => ({
      schemaVersion: BUILD_TEMPLATE_SCHEMA_VERSION,
      template: localTemplate,
      templates: listBuildTemplates()
    }),
    validate: (data) => !!(data && data.template)
  })
  if (!result.fromFallback) {
    const remoteTemplates = remoteTemplatesFromPayload(result.payload)
    const merged = mergeRemoteBuildTemplates(remoteTemplates)
    const syncedTemplate = merged.find((item) => remoteTemplates.some((remote) => templateMatches(item, remote))) || localTemplate
    return {
      ...result,
      payload: {
        ...result.payload,
        template: syncedTemplate,
        templates: merged
      }
    }
  }
  return result
}

async function deleteBuildTemplateRemote(id) {
  const templateId = normalizeString(id)
  const deletedLocally = deleteBuildTemplate(templateId)
  return requestJson(`/api/me/build-templates?id=${encodeURIComponent(templateId)}`, {
    method: 'DELETE',
    auth: true,
    fallback: () => ({ id: templateId, deleted: deletedLocally }),
    validate: (data) => !!(data && data.deleted)
  })
}

function templateModule(type, title, emptyText) {
  const templates = listBuildTemplates(type)
  return {
    type,
    title,
    count: templates.length,
    emptyText,
    recent: templates.slice(0, 3)
  }
}

function buildTemplateSummary() {
  return [
    templateModule('talent', '天赋模板', '还没有保存天赋模板'),
    templateModule('gear', '装备模板', '还没有保存装备模板')
  ]
}

module.exports = {
  BUILD_TEMPLATE_STORAGE_KEY,
  BUILD_TEMPLATE_SCHEMA_VERSION,
  buildTemplateSummary,
  deleteBuildTemplate,
  deleteBuildTemplateRemote,
  fetchBuildTemplates,
  listBuildTemplates,
  mergeRemoteBuildTemplates,
  syncBuildTemplate,
  saveBuildTemplate
}
