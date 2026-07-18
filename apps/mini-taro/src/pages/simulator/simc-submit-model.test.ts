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
  heroKey: '', heroLabel: '', scenarioKey: 'single', scenarioTitle: '单体', rawString: 'talents=',
  simcLines: [], status: 'ready', statusLabel: '本地', source: 'local', metadata: {},
  createdAt: '', updatedAt: '', remote: false, schemaVersion: 1,
  trust: { level: 'local_only', reason: '仅保存在当前设备' },
}

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

  it('keeps unavailable and empty backend options visibly non-ready', () => {
    const blocked = modelExports.deriveSimcOptionsView({
      contractRevision: 'simc-options-v1', status: 'blocked',
      races: { status: 'blocked', defaultKey: '', supportedKeys: [], defaultByClass: {} },
      scenarios: [],
      preparation: { schemaRevision: 'simc-preparation-v1', status: 'blocked', rows: [] },
    }, 'mage', 'frost', '', '')
    const empty = modelExports.deriveSimcOptionsView({
      contractRevision: 'simc-options-v1', status: 'ready',
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
      authoredAgainst: { manifestRevision: 'manifest-r1' },
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
      buildContext: { classKey: 'mage', specKey: 'frost', selectionIntent },
      classKey: 'mage', specKey: 'frost', raceKey: 'zandalari_troll',
      scenarioKey: 'backend_raid', talentTemplate: { ...localTemplate, rawString: 'talents=CAE_CANONICAL' },
    })).toMatchObject({ profileContext: { talents: 'talents=CAE_CANONICAL' } })
  })
})
