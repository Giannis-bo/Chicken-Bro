import { storageKey } from '@wow-mini/domain'
import { taroStorage, type StorageAdapter } from '@wow-mini/api-client'

import { emptyBuildsHomeContext, type BuildsHomeContext, type SpecSelection } from './build-context'

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseBuildsHomeContext(value: unknown): BuildsHomeContext | null {
  if (typeof value !== 'string') return null
  try {
    const parsed: unknown = JSON.parse(value)
    if (!isRecord(parsed) || !isRecord(parsed['lastSpecByClass'])) return null
    if (parsed['selectedClassKey'] !== undefined && !isNonEmptyString(parsed['selectedClassKey'])) return null
    const lastSpecByClass: Record<string, string> = {}
    for (const [classKey, specId] of Object.entries(parsed['lastSpecByClass'])) {
      if (!isNonEmptyString(classKey) || !isNonEmptyString(specId)) return null
      lastSpecByClass[classKey] = specId
    }
    return {
      ...(isNonEmptyString(parsed['selectedClassKey']) ? { selectedClassKey: parsed['selectedClassKey'] } : {}),
      lastSpecByClass,
    }
  } catch {
    return null
  }
}

function writeBuildsHomeContext(context: BuildsHomeContext, storage: StorageAdapter): BuildsHomeContext {
  storage.set(storageKey('builds.homeContext'), JSON.stringify(context))
  return context
}

export function readBuildsHomeContext(storage: StorageAdapter = taroStorage): BuildsHomeContext {
  return parseBuildsHomeContext(storage.get<unknown>(storageKey('builds.homeContext'))) ?? emptyBuildsHomeContext()
}

export function selectBuildsHomeClass(classKey: string, storage: StorageAdapter = taroStorage): BuildsHomeContext {
  const current = readBuildsHomeContext(storage)
  const next: BuildsHomeContext = {
    ...(isNonEmptyString(classKey) ? { selectedClassKey: classKey } : {}),
    lastSpecByClass: current.lastSpecByClass,
  }
  return writeBuildsHomeContext(next, storage)
}

export function rememberBuildsHomeSpec(
  selection: Pick<SpecSelection, 'classKey' | 'specId'>,
  context: BuildsHomeContext = emptyBuildsHomeContext(),
  storage: StorageAdapter = taroStorage,
): BuildsHomeContext {
  const next: BuildsHomeContext = {
    ...(isNonEmptyString(selection.classKey) ? { selectedClassKey: selection.classKey } : {}),
    lastSpecByClass: {
      ...context.lastSpecByClass,
      ...(isNonEmptyString(selection.classKey) && isNonEmptyString(selection.specId)
        ? { [selection.classKey]: selection.specId }
        : {}),
    },
  }
  return writeBuildsHomeContext(next, storage)
}
