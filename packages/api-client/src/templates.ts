import {
  storageKey,
  trustForBackend,
  trustForLocal,
  type BuildTemplate,
  type BuildTemplateType,
} from '@wow-mini/domain'

import { cleanString, isRecord } from './guards'
import { taroStorage, type StorageAdapter } from './storage'
import type { ApiResult, ApiTransport } from './transport'

const schemaVersion = 1 as const
const validTypes = new Set<BuildTemplateType>(['talent', 'gear'])

function isRemoteTemplatePayload(value: unknown): boolean {
  if (!isRecord(value)) return false
  const record = value
  const textFields = [
    'id', 'clientId', 'type', 'title', 'classKey', 'className', 'specKey', 'specName',
    'heroKey', 'heroLabel', 'scenarioKey', 'scenarioTitle', 'rawString', 'status',
    'statusLabel', 'source', 'createdAt', 'updatedAt',
  ] as const
  return cleanString(record['id']).length > 0
    && validTypes.has(cleanString(record['type']) as BuildTemplateType)
    && cleanString(record['rawString']).length > 0
    && record['schemaVersion'] === schemaVersion
    && record['remote'] === true
    && textFields.every((field) => typeof record[field] === 'string')
    && Array.isArray(record['simcLines'])
    && record['simcLines'].every((line) => typeof line === 'string')
    && isRecord(record['metadata'])
}

function isTemplateListPayload(value: unknown): boolean {
  return isRecord(value)
    && value['schemaVersion'] === schemaVersion
    && Array.isArray(value['templates'])
    && value['templates'].every(isRemoteTemplatePayload)
}

function isTemplateMutationPayload(value: unknown): boolean {
  return isRecord(value)
    && isTemplateListPayload(value)
    && isRemoteTemplatePayload(value['template'])
}

export interface BuildTemplateInput {
  id?: string
  clientId?: string
  type: BuildTemplateType
  title?: string
  classKey?: string
  className?: string
  specKey?: string
  specName?: string
  heroKey?: string
  heroLabel?: string
  scenarioKey?: string
  scenarioTitle?: string
  rawString: string
  simcLines?: readonly string[]
  status?: string
  statusLabel?: string
  source?: string
  metadata?: Readonly<Record<string, unknown>>
  createdAt?: string
  updatedAt?: string
  remote?: boolean
}

export interface TemplateListPayload {
  schemaVersion: 1
  templates: readonly BuildTemplate[]
}

export interface TemplateMutationPayload extends TemplateListPayload {
  template: BuildTemplate | null
}

export interface TemplateDeletePayload {
  id: string
  deleted: boolean
}

export interface TemplateClock {
  now(): number
  random(): number
}

const systemClock: TemplateClock = { now: () => Date.now(), random: () => Math.random() }

function statusLabel(type: BuildTemplateType, status: string): string {
  const labels: Readonly<Record<string, string>> = {
    saved: '已保存', complete: '完整配置', encoded: '已编码', simc_ready: 'SimC-ready',
    partial: '缺字段', blocked: '不可计算',
  }
  return labels[status] ?? (type === 'gear' ? '不可计算' : '待编码')
}

function parseStoredTemplates(storage: StorageAdapter): readonly unknown[] {
  const stored = storage.get<unknown>(storageKey('templates.local'))
  if (Array.isArray(stored)) return stored
  if (typeof stored !== 'string' || !stored) return []
  try {
    const parsed: unknown = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function sorted(values: readonly BuildTemplate[]): readonly BuildTemplate[] {
  return [...values].sort((left, right) => {
    const leftTime = Date.parse(left.updatedAt || left.createdAt) || 0
    const rightTime = Date.parse(right.updatedAt || right.createdAt) || 0
    return rightTime - leftTime
  })
}

function templateMatches(left: BuildTemplate, right: BuildTemplate): boolean {
  if (left.id && right.id && left.id === right.id) return true
  if (left.id && right.clientId && left.id === right.clientId) return true
  if (left.clientId && right.id && left.clientId === right.id) return true
  return left.type === right.type && left.rawString === right.rawString
}

export class TemplateRepository {
  constructor(
    private readonly transport: ApiTransport,
    private readonly storage: StorageAdapter = taroStorage,
    private readonly clock: TemplateClock = systemClock,
  ) {}

  private randomId(type: BuildTemplateType): string {
    return `${type}-${this.clock.now().toString(36)}-${this.clock.random().toString(36).slice(2, 10)}`
  }

  private normalize(value: unknown, existing?: BuildTemplate, forceRemote = false): BuildTemplate | null {
    if (!isRecord(value)) return null
    const type = cleanString(value['type']) as BuildTemplateType
    if (!validTypes.has(type)) return null
    const rawString = cleanString(value['rawString'])
    if (!rawString) return null
    const now = new Date(this.clock.now()).toISOString()
    const className = cleanString(value['className'])
    const specName = cleanString(value['specName'])
    const scenarioTitle = cleanString(value['scenarioTitle'])
    const fallbackTitle = [`${specName}${className}`, scenarioTitle].filter(Boolean).join(' · ')
    const status = cleanString(value['status']) || (type === 'gear' ? 'complete' : 'saved')
    const remote = forceRemote || value['remote'] === true
    return {
      id: existing?.id || cleanString(value['id']) || this.randomId(type),
      clientId: cleanString(value['clientId']),
      type,
      title: cleanString(value['title']) || fallbackTitle || (type === 'talent' ? '天赋模板' : '装备模板'),
      classKey: cleanString(value['classKey']),
      className,
      specKey: cleanString(value['specKey']),
      specName,
      heroKey: cleanString(value['heroKey']),
      heroLabel: cleanString(value['heroLabel']),
      scenarioKey: cleanString(value['scenarioKey']),
      scenarioTitle,
      rawString,
      simcLines: Array.isArray(value['simcLines']) ? value['simcLines'].map(cleanString).filter(Boolean) : [],
      status,
      statusLabel: cleanString(value['statusLabel']) || statusLabel(type, status),
      source: cleanString(value['source']) || (type === 'talent' ? 'WebSim 天赋模拟器' : '装备模拟器'),
      metadata: isRecord(value['metadata']) ? value['metadata'] : {},
      createdAt: existing?.createdAt || cleanString(value['createdAt']) || now,
      updatedAt: cleanString(value['updatedAt']) || now,
      remote,
      schemaVersion,
      trust: remote ? trustForBackend() : trustForLocal(),
    }
  }

  private persist(values: readonly BuildTemplate[]): void {
    this.storage.set(storageKey('templates.local'), JSON.stringify(sorted(values)))
  }

  list(type?: BuildTemplateType): readonly BuildTemplate[] {
    const values = parseStoredTemplates(this.storage)
      .map((value) => this.normalize(value))
      .filter((value): value is BuildTemplate => value !== null)
    return sorted(type ? values.filter((value) => value.type === type) : values)
  }

  saveLocal(input: BuildTemplateInput): BuildTemplate | null {
    const values = this.list()
    const existing = values.find((value) => value.type === input.type && value.rawString === input.rawString)
    const template = this.normalize(input, existing)
    if (!template) return null
    this.persist(existing
      ? values.map((value) => value.id === existing.id ? template : value)
      : [...values, template])
    return template
  }

  deleteLocal(id: string): boolean {
    const values = this.list()
    const next = values.filter((value) => value.id !== id)
    this.persist(next)
    return next.length !== values.length
  }

  private mergeRemote(remoteValues: readonly unknown[]): readonly BuildTemplate[] {
    const merged = [...this.list()]
    for (const value of remoteValues) {
      const remote = this.normalize(value, undefined, true)
      if (!remote) continue
      const index = merged.findIndex((candidate) => templateMatches(candidate, remote))
      if (index >= 0) merged[index] = remote
      else merged.push(remote)
    }
    this.persist(merged)
    return this.list()
  }

  async fetch(type?: BuildTemplateType): Promise<ApiResult<TemplateListPayload>> {
    const path = type
      ? `/api/me/build-templates?type=${encodeURIComponent(type)}`
      : '/api/me/build-templates'
    const result = await this.transport.requestEndpoint<TemplateListPayload>('templates.list', path, {
      fallback: () => ({ schemaVersion, templates: this.list(type) }),
      validate: isTemplateListPayload,
    })
    if (result.fromFallback) return result
    const templates = this.mergeRemote(result.payload.templates)
    return { ...result, payload: { schemaVersion, templates: type ? templates.filter((item) => item.type === type) : templates } }
  }

  async upsert(input: BuildTemplateInput): Promise<ApiResult<TemplateMutationPayload>> {
    const local = this.saveLocal(input)
    if (!local) {
      return {
        payload: { schemaVersion, template: null, templates: this.list() },
        fromFallback: true,
        error: 'invalid build template',
      }
    }
    const result = await this.transport.requestEndpoint<TemplateMutationPayload>('templates.upsert', '/api/me/build-templates', {
      data: { template: local },
      fallback: () => ({ schemaVersion, template: local, templates: this.list() }),
      validate: isTemplateMutationPayload,
    })
    if (result.fromFallback) return result
    const remoteValues = [result.payload.template, ...result.payload.templates].filter(Boolean)
    const templates = this.mergeRemote(remoteValues)
    const template = templates.find((candidate) => candidate.id === result.payload.template?.id)
      ?? templates.find((candidate) => templateMatches(candidate, local))
      ?? local
    return { ...result, payload: { schemaVersion, template, templates } }
  }

  async delete(id: string): Promise<ApiResult<TemplateDeletePayload>> {
    const deletedLocally = this.deleteLocal(id)
    return this.transport.requestEndpoint('templates.delete', `/api/me/build-templates?id=${encodeURIComponent(id)}`, {
      fallback: () => ({ id, deleted: deletedLocally }),
      validate: (value) => isRecord(value) && value['id'] === id && value['deleted'] === true,
    })
  }
}
