import { describe, expect, it } from 'vitest'

import type { BuildTemplate } from '@wow-mini/domain'
import * as modelExports from './simc-submit-model'

import {
  simcBlockerRows,
  simcConfirmationLabel,
  simcSummaryRows,
  simcTemplateSlot,
} from './simc-submit-model'

const localTemplate: BuildTemplate = {
  id: 'local-talent', clientId: 'local-talent', type: 'talent', title: '本地天赋',
  classKey: 'mage', className: '法师', specKey: 'frost', specName: '冰霜',
  heroKey: '', heroLabel: '', scenarioKey: 'single', scenarioTitle: '单体', rawString: 'talents=CAE',
  simcLines: [], status: 'ready', statusLabel: '本地', source: 'local', metadata: {},
  createdAt: '', updatedAt: '', remote: false, schemaVersion: 1,
  trust: { level: 'local_only', reason: '仅保存在当前设备' },
}

const canonicalSelectionIntent = {
  schemaRevision: 'selection-intent-v1',
  authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
  eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
  slots: {},
} as const

describe('SimC submit truth model', () => {
  it('preserves empty template slots without inventing templates', () => {
    expect(simcTemplateSlot('talent', [], '')).toMatchObject({
      valueLabel: '未选择天赋模板',
      helperLabel: '尚未保存模板',
      state: 'blocked',
      options: [],
    })
  })

  it('keeps local templates distinct from synchronized templates', () => {
    expect(simcTemplateSlot('talent', [localTemplate], localTemplate.id)).toMatchObject({
      valueLabel: '本地天赋',
      helperLabel: '仅保存在本机',
      state: 'partial',
    })
  })

  it('derives six summary rows and five blockers from real readiness', () => {
    const input = {
      specializationLabel: '冰霜法师', raceLabel: '人类', scenarioLabel: '单体', durationSeconds: 300,
      talentTemplate: localTemplate, activeTaskCount: 0, confirmationState: 'unknown' as const,
    }
    expect(simcSummaryRows(input)).toHaveLength(6)
    const blockers = simcBlockerRows(input)
    expect(blockers).toHaveLength(5)
    expect(blockers.find((row) => row.id === 'gear')?.blocked).toBe(true)
    expect(blockers.find((row) => row.id === 'validation')?.blocked).toBe(true)
    expect(simcBlockerRows({ ...input, confirmationState: 'ready' })
      .find((row) => row.id === 'validation')?.detail).toBe('后端已确认当前组合')
  })

  it('treats the canonical gear handoff as local intent pending a fresh backend snapshot', () => {
    const input = {
      specializationLabel: '冰霜法师', raceLabel: 'human', scenarioLabel: '后端单体',
      scenarioTargets: 1, durationSeconds: 300, talentTemplate: localTemplate,
      gearContextAvailable: true, gearContextLabel: '冰霜 · canonical intent 已带入',
      activeTaskCount: 0, confirmationState: 'unknown' as const,
    }

    expect(simcSummaryRows(input).find((row) => row.id === 'gear')).toMatchObject({
      value: '冰霜 · canonical intent 已带入', state: 'partial',
    })
    expect(simcBlockerRows(input).find((row) => row.id === 'gear')).toMatchObject({
      blocked: false, detail: '冰霜 · canonical intent 已带入；等待本次后端快照校验',
    })
  })

  it('keeps an HTTP or unauthenticated talent fallback local-only without staling the canonical page', () => {
    const routeFromFallback = (modelExports as Readonly<Record<string, unknown>>)['simcRouteFromFallback'] as
      | ((input: Readonly<Record<string, boolean>>) => boolean)
      | undefined
    const canPrepare = (modelExports as Readonly<Record<string, unknown>>)['simcCanPrepare'] as
      | ((input: Readonly<Record<string, unknown>>) => boolean)
      | undefined
    const selectionIntent = {
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {},
    }
    const canonical = modelExports.buildCanonicalSimcContext({
      buildContext: { classKey: 'mage', specKey: 'frost', selectionIntent },
      classKey: 'mage', specKey: 'frost', raceKey: 'human', scenarioKey: 'single',
      talentTemplate: localTemplate,
    })

    expect(routeFromFallback).toBeTypeOf('function')
    expect(canPrepare).toBeTypeOf('function')
    if (!routeFromFallback || !canPrepare) return
    expect(routeFromFallback({
      homeFromFallback: false,
      optionsFromFallback: false,
      talentsFromFallback: true,
      tasksFromFallback: false,
    })).toBe(false)
    expect(simcTemplateSlot('talent', [localTemplate], localTemplate.id).state).toBe('partial')
    expect(canonical).not.toBeNull()
    expect(canPrepare({
      routeState: 'ready', optionsState: 'ready', canonicalContextAvailable: Boolean(canonical),
      activeTaskCount: 0, submitting: false,
    })).toBe(true)
  })

  it('invalidates async work on input revision changes and unmount', () => {
    const createSession = (modelExports as Readonly<Record<string, unknown>>)['createSimcSubmissionSession'] as
      | (() => {
        begin: () => unknown
        invalidate: () => void
        mount: () => void
        unmount: () => void
        isCurrent: (token: unknown) => boolean
      })
      | undefined

    expect(createSession).toBeTypeOf('function')
    if (!createSession) return
    const session = createSession()
    const first = session.begin()
    expect(session.isCurrent(first)).toBe(true)
    session.invalidate()
    expect(session.isCurrent(first)).toBe(false)
    const second = session.begin()
    expect(session.isCurrent(second)).toBe(true)
    session.unmount()
    expect(session.isCurrent(second)).toBe(false)
    session.mount()
    const third = session.begin()
    expect(session.isCurrent(third)).toBe(true)
  })

  it('does not claim a result before a returned task id exists', () => {
    expect(simcConfirmationLabel('ready', false, '')).toEqual({
      title: '组合校验通过', detail: '可提交真实任务', state: 'ready',
    })
    expect(simcConfirmationLabel('unknown', false, 'task-verified')).toEqual({
      title: '任务已提交', detail: 'task-verified', state: 'ready',
    })
  })

  it('derives race, scenario, duration, targets, and preparation only from backend options', () => {
    const derive = (modelExports as Readonly<Record<string, unknown>>)['deriveSimcOptionsView'] as
      | ((...args: readonly unknown[]) => Readonly<Record<string, unknown>>)
      | undefined

    expect(derive).toBeTypeOf('function')
    if (!derive) return
    const view = derive({
      contractRevision: 'simc-options-v1',
      status: 'ready',
      specializationPolicy: {
        contractRevision: 'simc-execution-support-v1',
        status: 'ready',
        supportedSpecCount: 26,
        unsupportedSpecCount: 14,
        unsupportedSpecializations: [{
          specializationId: 'evoker:augmentation',
          role: 'support',
          code: 'SIMC_SPECIALIZATION_UNSUPPORTED',
        }],
      },
      races: {
        status: 'supported',
        defaultKey: 'zandalari_troll',
        supportedKeys: ['zandalari_troll'],
        defaultByClass: { mage: 'zandalari_troll' },
      },
      scenarios: [{
        key: 'backend_raid', label: 'Backend raid', fightStyle: 'Patchwerk',
        targets: 7, durationSeconds: 417, status: 'supported',
      }],
      preparation: {
        schemaRevision: 'simc-preparation-v1', status: 'ready',
        rows: [
          {
            key: 'global', category: 'raid', label: 'Global', defaultState: 'disabled',
            evidenceState: 'verified', overrideSupported: true,
          },
          {
            key: 'mage', category: 'class', classKey: 'mage', label: 'Mage',
            defaultState: 'enabled', evidenceState: 'verified', overrideSupported: true,
          },
          {
            key: 'shaman', category: 'class', classKey: 'shaman', label: 'Shaman',
            defaultState: 'enabled', evidenceState: 'verified', overrideSupported: false,
          },
        ],
      },
    }, 'mage', 'frost', '', '')

    expect(view).toMatchObject({
      state: 'ready',
      selectedRaceKey: 'zandalari_troll',
      selectedScenarioKey: 'backend_raid',
      durationSeconds: 417,
      targets: 7,
    })
    expect(view['races']).toEqual([{ id: 'zandalari_troll', label: 'zandalari_troll' }])
    expect(view['scenarios']).toEqual([{ id: 'backend_raid', label: 'Backend raid' }])
    expect(view['preparationRows']).toEqual([
      expect.objectContaining({ key: 'global', overrideSupported: true }),
      expect.objectContaining({ key: 'mage', overrideSupported: true }),
    ])
  })

  it('blocks unsupported tank, healer, and augmentation specs before stat snapshot work', () => {
    const view = modelExports.deriveSimcOptionsView({
      contractRevision: 'simc-options-v1',
      status: 'ready',
      specializationPolicy: {
        contractRevision: 'simc-execution-support-v1',
        status: 'ready',
        supportedSpecCount: 26,
        unsupportedSpecCount: 14,
        unsupportedSpecializations: [{
          specializationId: 'paladin:holy',
          role: 'healer',
          code: 'SIMC_SPECIALIZATION_UNSUPPORTED',
        }],
      },
      races: {
        status: 'supported', defaultKey: 'human', supportedKeys: ['human'],
        defaultByClass: { paladin: 'human' },
      },
      scenarios: [{
        key: 'single', label: '单体', fightStyle: 'Patchwerk',
        targets: 1, durationSeconds: 300, status: 'supported',
      }],
      preparation: {
        schemaRevision: 'simc-preparation-v1', status: 'ready',
        rows: [{
          key: 'global', category: 'raid', label: 'Global', defaultState: 'disabled',
          evidenceState: 'verified', overrideSupported: true,
        }],
      },
    }, 'paladin', 'holy', '', '')

    expect(view).toMatchObject({
      state: 'blocked',
      specializationSupported: false,
      specializationBlockerCode: 'SIMC_SPECIALIZATION_UNSUPPORTED',
    })
  })

  it('keeps unavailable and empty backend options visibly non-ready', () => {
    const blocked = modelExports.deriveSimcOptionsView({
      contractRevision: 'simc-options-v1', status: 'blocked',
      specializationPolicy: {
        contractRevision: 'simc-execution-support-v1', status: 'blocked',
        supportedSpecCount: 0, unsupportedSpecCount: 0, unsupportedSpecializations: [],
      },
      races: { status: 'blocked', defaultKey: '', supportedKeys: [], defaultByClass: {} },
      scenarios: [],
      preparation: { schemaRevision: 'simc-preparation-v1', status: 'blocked', rows: [] },
    }, 'mage', 'frost', '', '')
    const empty = modelExports.deriveSimcOptionsView({
      contractRevision: 'simc-options-v1', status: 'ready',
      specializationPolicy: {
        contractRevision: 'simc-execution-support-v1', status: 'ready',
        supportedSpecCount: 26, unsupportedSpecCount: 14, unsupportedSpecializations: [],
      },
      races: { status: 'supported', defaultKey: 'human', supportedKeys: ['human'], defaultByClass: {} },
      scenarios: [],
      preparation: {
        schemaRevision: 'simc-preparation-v1', status: 'ready',
        rows: [{
          key: 'backend', category: 'backend', label: 'Backend', defaultState: 'disabled',
          evidenceState: 'verified', overrideSupported: false,
        }],
      },
    }, 'mage', 'frost', '', '')

    expect(blocked).toMatchObject({ state: 'blocked', races: [], scenarios: [], preparationRows: [] })
    expect(empty).toMatchObject({ state: 'empty', selectedScenarioKey: '', durationSeconds: undefined })
  })

  it('builds canonical selectionIntent and profileContext from the gear handoff and talent source', () => {
    const build = (modelExports as Readonly<Record<string, unknown>>)['buildCanonicalSimcContext'] as
      | ((...args: readonly unknown[]) => Readonly<Record<string, unknown>> | null)
      | undefined
    const selectionIntent = {
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {},
    }

    expect(build).toBeTypeOf('function')
    if (!build) return
    expect(build({
      buildContext: { classKey: 'mage', specKey: 'frost', selectionIntent },
      classKey: 'mage', specKey: 'frost', raceKey: 'zandalari_troll',
      scenarioKey: 'backend_raid', talentTemplate: { ...localTemplate, rawString: 'websim:mage:frost::root:1' },
    })).toEqual({
      selectionIntent,
      profileContext: {
        classKey: 'mage', specKey: 'frost',
        race: 'zandalari_troll', scenarioKey: 'backend_raid',
        talents: 'websim:mage:frost::root:1',
      },
    })
    expect(build({
      buildContext: { classKey: 'shaman', specKey: 'elemental', selectionIntent },
      classKey: 'mage', specKey: 'frost', raceKey: 'zandalari_troll',
      scenarioKey: 'backend_raid', talentTemplate: localTemplate,
    })).toBeNull()
    expect(build({
      buildContext: {
        classKey: 'mage', specKey: 'frost',
        selectionIntent: { ...selectionIntent, schemaRevision: 'selection-intent-v0' },
      },
      classKey: 'mage', specKey: 'frost', raceKey: 'zandalari_troll',
      scenarioKey: 'backend_raid', talentTemplate: localTemplate,
    })).toBeNull()
    expect(build({
      buildContext: { classKey: 'mage', specKey: 'frost', selectionIntent },
      classKey: 'mage', specKey: 'frost', raceKey: 'zandalari_troll',
      scenarioKey: 'backend_raid', talentTemplate: { ...localTemplate, rawString: 'talents=CAE_CANONICAL' },
    })).toMatchObject({ profileContext: { talents: 'talents=CAE_CANONICAL' } })
  })

  it('offers only canonical gear handoffs or typed gear templates with a valid selection intent', () => {
    const sources = modelExports.simcGearSources({
      buildContext: {
        classKey: 'mage', specKey: 'frost', specName: '冰霜',
        selectionIntent: canonicalSelectionIntent,
      },
      templates: [
        {
          ...localTemplate,
          id: 'gear-valid', type: 'gear', title: '已验证装备模板', remote: true,
          metadata: { selectionIntent: canonicalSelectionIntent },
        },
        {
          ...localTemplate,
          id: 'gear-missing-intent', type: 'gear', title: '缺少意图',
          metadata: {},
        },
        {
          ...localTemplate,
          id: 'gear-wrong-spec', type: 'gear', title: '其他专精', specKey: 'fire',
          metadata: { selectionIntent: canonicalSelectionIntent },
        },
      ],
      classKey: 'mage', specKey: 'frost', specializationLabel: '冰霜法师',
    })

    expect(sources.map((source) => source.id)).toEqual(['handoff', 'template:gear-valid'])
    expect(sources[0]).toMatchObject({ state: 'partial', label: '冰霜法师 · 装备详情带入' })
    expect(sources[1]).toMatchObject({ state: 'ready', label: '已验证装备模板' })
    expect(sources[1]?.buildContext.selectionIntent).toEqual(canonicalSelectionIntent)
  })

  it('does not manufacture a SimC gear context from template display fields or raw JSON alone', () => {
    const sources = modelExports.simcGearSources({
      templates: [{
        ...localTemplate,
        id: 'gear-raw-only', type: 'gear', title: '只有 rawString',
        rawString: JSON.stringify({ head: { itemId: 123 } }), metadata: {},
      }],
      classKey: 'mage', specKey: 'frost', specializationLabel: '冰霜法师',
    })

    expect(sources).toEqual([])
  })
})
