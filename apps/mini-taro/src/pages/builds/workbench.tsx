import Taro, { useRouter } from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { EvidenceLedger } from '@wow-mini/design-system/components/EvidenceLedger'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteColumn, RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import {
  WorkbenchModuleDeck,
  WorkbenchReadinessPanel,
  WorkbenchSpecSummary,
  type WorkbenchModuleCard,
} from '@wow-mini/design-system/components/WorkbenchComponents'

import {
  defaultSpecId,
  findSpecSelection,
  flattenSpecs,
  scenarioOptions,
} from '../_shared/build-context'
import {
  goBack,
  navigateTo,
  useAsyncRoute,
  safeDecode,
} from '../_shared/route-runtime'
import {
  buildCurrentSpecWorkbenchModel,
  type CurrentSpecWorkbenchPayload,
} from './workbench-model'
import styles from './workbench.module.scss'

function routeForModule(id: string): string {
  if (id === 'talents') return '/pages/builds/talent-simulator'
  if (id === 'gear') return '/pages/builds/detail'
  if (id === 'simc') return '/pages/simulator/simc'
  if (id === 'assistant') return '/pages/simulator/chickenbro'
  return '/pages/profile/profile'
}

export default function WorkbenchPage() {
  const router = useRouter()
  const initialSpec = safeDecode(router.params['spec']) || defaultSpecId
  const [selectedSpecId, setSelectedSpecId] = useState(initialSpec)
  const [scenarioIndex, setScenarioIndex] = useState(0)
  const selectionChanged = useRef(false)
  const route = useAsyncRoute<CurrentSpecWorkbenchPayload>(async () => {
    const homeResult = await wowApi.builds.home()
    const selection = findSpecSelection(homeResult.payload, selectedSpecId)
    if (!selection) {
      throw new Error('没有可用的职业专精映射')
    }
    const [talentResult, gearResult, talentTemplates, gearTemplates] = await Promise.all([
      wowApi.websim.talents({ classKey: selection.classKey, specKey: selection.specKey, heroKey: selection.heroKey }),
      wowApi.websim.gear({
        classKey: selection.classKey,
        specKey: selection.specKey,
        compact: true,
        mode: 'initial',
      }),
      wowApi.templates.fetch('talent'),
      wowApi.templates.fetch('gear'),
    ])
    const errors = [homeResult.error, talentResult.error, gearResult.error].filter(Boolean)
    return {
      payload: {
        home: homeResult.payload,
        talents: talentResult.payload,
        gear: gearResult.payload,
        talentTemplates: talentTemplates.payload.templates,
        gearTemplates: gearTemplates.payload.templates,
        sources: {
          home: { fromFallback: homeResult.fromFallback, error: homeResult.error },
          talents: { fromFallback: talentResult.fromFallback, error: talentResult.error },
          gear: { fromFallback: gearResult.fromFallback, error: gearResult.error },
          talentTemplates: { fromFallback: talentTemplates.fromFallback, error: talentTemplates.error },
          gearTemplates: { fromFallback: gearTemplates.fromFallback, error: gearTemplates.error },
        },
      },
      fromFallback: homeResult.fromFallback || talentResult.fromFallback || gearResult.fromFallback,
      error: errors.join(' / '),
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (!selectionChanged.current) {
      selectionChanged.current = true
      return
    }
    void route.load()
  }, [selectedSpecId, route.load])

  const data = route.data
  const model = buildCurrentSpecWorkbenchModel({
    ...(data ? { payload: data } : {}),
    routeState: route.state.state,
    selectedSpecId,
    ...(scenarioOptions[scenarioIndex]?.key ? { scenarioKey: scenarioOptions[scenarioIndex].key } : {}),
  })
  const modules: readonly WorkbenchModuleCard[] = model.modules
  const evidence = model.evidence.map((row) => ({
    id: row.id,
    label: row.label,
    value: row.value,
    state: row.state,
    sourceCountLabel: row.sourceCountLabel,
    blockerCountLabel: row.blockerCountLabel,
    revisionLabel: row.revisionLabel,
    actionLabel: row.actionLabel,
    region: `ledger_table.${row.id}`,
  }))

  const openModule = (module: WorkbenchModuleCard) => {
    if (!data) return
    const path = routeForModule(module.id)
    if (path === '/pages/profile/profile') {
      void Taro.switchTab({ url: path })
      return
    }
    navigateTo(path, {
      spec: model.selection?.specId,
      classKey: model.selection?.classKey,
      specKey: model.selection?.specKey,
      scenario: scenarioOptions[scenarioIndex]?.key,
      ...(module.id === 'gear' ? { query: 'gear' } : {}),
      from: 'workbench',
    })
  }

  const allSpecs = data ? flattenSpecs(data.home.classOptions) : []
  const labels = allSpecs.map((entry) => entry.spec.title || `${entry.spec.specName || entry.spec.name}${entry.classItem.name}`)
  const selectedIndex = Math.max(0, allSpecs.findIndex((entry) => (
    entry.spec.id === model.selection?.specId || entry.spec.specId === model.selection?.specId
  )))
  const scenarioLabels = scenarioOptions.map((entry) => entry.title)

  const handlePrimary = () => {
    if (model.primaryAction.kind === 'retry') {
      void route.load()
      return
    }
    const module = modules.find((item) => item.id === model.primaryAction.moduleId)
    if (module) openModule(module)
  }

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.builds-surface-texture"
    >
      <PageFrame
        region="top_bar"
        title="专精工作台"
        variant="workbench"
        onBack={() => goBack('/pages/builds/builds')}
      >
        <RouteColumn className={styles['surface'] ?? ''} routeState={route.state.state}>
          <RouteRegion className={`${styles['region'] ?? ''} ${styles['hero'] ?? ''}`} data-region="workbench_hero">
            <WorkbenchSpecSummary
              contextDetail={model.contextDetail}
              identity={model.identity}
              scenarioDisabled={model.initialLoading}
              scenarioIndex={scenarioIndex}
              scenarioLabels={scenarioLabels}
              selectionDisabled={!data || !allSpecs.length}
              selectionIndex={selectedIndex}
              selectionLabels={labels}
              sourceLabel={model.identitySourceLabel}
              state={model.identityState}
              title={model.title}
              onScenarioChange={setScenarioIndex}
              onSelectionChange={(index) => {
                const next = allSpecs[index]
                if (next?.spec.id) setSelectedSpecId(next.spec.id)
              }}
            />
          </RouteRegion>
          <RouteRegion className={`${styles['region'] ?? ''} ${styles['readiness'] ?? ''}`} data-region="readiness_summary">
            <WorkbenchReadinessPanel
              headline={model.readinessHeadline}
              primaryAction={{ label: model.primaryAction.label, disabled: model.primaryAction.disabled }}
              reasons={model.readinessReasons}
              state={model.overallState}
              statusLabel={model.overallLabel}
              onPrimary={handlePrimary}
            />
          </RouteRegion>
          <RouteRegion className={`${styles['region'] ?? ''} ${styles['modules'] ?? ''}`} data-region="module_grid">
            <WorkbenchModuleDeck modules={modules} onModule={openModule} />
          </RouteRegion>
          <RouteRegion className={`${styles['region'] ?? ''} ${styles['ledger'] ?? ''}`} data-region="evidence_ledger">
            <EvidenceLedger
              region="ledger_table"
              rows={evidence}
              title="Evidence Ledger"
              variant="workbench"
              onSource={(row) => {
                const module = modules.find((item) => item.id === row.id)
                if (module) openModule(module)
              }}
            />
          </RouteRegion>
        </RouteColumn>
      </PageFrame>
    </AppShell>
  )
}
