import type { BuildsHomePayload, ReadinessState } from '@wow-mini/domain'
import type { ProductionAssetId } from '@wow-mini/assets-manifest'

import {
  emptyBuildsHomeContext,
  resolveBuildsHomeLaunch,
  type BuildsHomeContext,
} from '../_shared/build-context'

export type BuildsHomeCommandId = 'talents' | 'gear' | 'simc' | 'tasks'

export interface BuildsHomeClassOption {
  classKey: string
  label: string
  iconUrl?: string
  disabled: boolean
  selected: boolean
}

export interface BuildsHomeCommandItem {
  id: BuildsHomeCommandId
  title: '天赋模拟' | '装备模拟' | 'SimC 模拟' | '任务查看'
  detail: string
  glyphAssetId: ProductionAssetId
  fallbackGlyphAssetId: ProductionAssetId
  specId?: string
  disabled: boolean
}

export interface BuildsHomeViewModel {
  classOptions: readonly BuildsHomeClassOption[]
  selectedClassKey?: string
  launchSpecId?: string
  commandItems: readonly BuildsHomeCommandItem[]
}

export interface BuildBuildsHomeModelInput {
  payload?: BuildsHomePayload
  routeState: ReadinessState
  context: BuildsHomeContext
}

const commandDefinitions = [
  {
    id: 'talents',
    title: '天赋模拟',
    detail: '设计、导入与保存天赋模板',
    glyphAssetId: 'builds-evidence-medallion.talents',
    fallbackGlyphAssetId: 'quick-action-talents-glyph.default',
  },
  {
    id: 'gear',
    title: '装备模拟',
    detail: '搭配装备与增强方案',
    glyphAssetId: 'builds-evidence-medallion.gear',
    fallbackGlyphAssetId: 'quick-action-gear-glyph.default',
  },
  {
    id: 'simc',
    title: 'SimC 模拟',
    detail: '组合模板并发起模拟',
    glyphAssetId: 'builds-evidence-medallion.simc',
    fallbackGlyphAssetId: 'quick-action-simc-glyph.default',
  },
  {
    id: 'tasks',
    title: '任务查看',
    detail: '查看模拟任务与结果',
    glyphAssetId: 'builds-evidence-medallion.tasks',
    fallbackGlyphAssetId: 'utility-glyph-family.records',
  },
] as const satisfies readonly Omit<BuildsHomeCommandItem, 'specId' | 'disabled'>[]

function hasValidSpecialization(classItem: BuildsHomePayload['classOptions'][number]): boolean {
  return classItem.specializations.length > 0
}

export function buildBuildsHomeModel({
  payload,
  context = emptyBuildsHomeContext(),
}: BuildBuildsHomeModelInput): BuildsHomeViewModel {
  const launch = payload ? resolveBuildsHomeLaunch(payload, context) : null
  const selectedClassKey = launch?.classKey
  const launchSpecId = launch?.selection.specId

  return {
    classOptions: (payload?.classOptions ?? []).map((classItem) => ({
      classKey: classItem.websimClassKey,
      label: classItem.name,
      ...(classItem.iconUrl ? { iconUrl: classItem.iconUrl } : {}),
      disabled: !hasValidSpecialization(classItem),
      selected: classItem.websimClassKey === selectedClassKey,
    })),
    ...(selectedClassKey ? { selectedClassKey } : {}),
    ...(launchSpecId ? { launchSpecId } : {}),
    commandItems: commandDefinitions.map((definition) => (
      definition.id === 'tasks'
        ? { ...definition, disabled: false }
        : { ...definition, ...(launchSpecId ? { specId: launchSpecId } : {}), disabled: !launchSpecId }
    )),
  }
}
