import { Picker } from '@tarojs/components'
import Taro, { usePullDownRefresh } from '@tarojs/taro'
import { useMemo, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import {
  BuildEvidenceNavigator,
  type BuildEvidenceItem,
} from '@wow-mini/design-system/components/BuildEvidenceNavigator'
import { BuildSpecializationOverview } from '@wow-mini/design-system/components/BuildSpecializationOverview'
import {
  BuildWorkflowTimeline,
  type BuildWorkflowStage,
} from '@wow-mini/design-system/components/BuildWorkflowTimeline'
import { BuildWorkspaceEntry } from '@wow-mini/design-system/components/BuildWorkspaceEntry'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteGrid, RouteRegion } from '@wow-mini/design-system/components/RouteFlow'

import { flattenSpecs } from '../_shared/build-context'
import { navigateTo, useAsyncRoute } from '../_shared/route-runtime'
import { buildBuildsHomeModel, type BuildsHomeEvidenceId } from './builds-home-model'
import styles from './builds-home.module.scss'

const evidenceRoutes: Readonly<Record<BuildsHomeEvidenceId, string>> = {
  talents: '/pages/builds/talent-simulator',
  gear: '/pages/builds/detail',
  simc: '/pages/simulator/simc',
  tasks: '/pages/simulator/tasks',
}

export default function BuildsHomePage() {
  const [selectedSpecId, setSelectedSpecId] = useState<string>()
  const route = useAsyncRoute(
    () => wowApi.builds.home(),
    {
      fallbackPolicy: 'blocked',
      isEmpty: (payload) => !payload.classOptions.some((classItem) => classItem.specializations.length > 0),
    },
  )

  usePullDownRefresh(() => {
    void route.load().finally(() => Taro.stopPullDownRefresh())
  })

  const model = useMemo(() => buildBuildsHomeModel({
    routeState: route.state.state,
    ...(route.data ? { payload: route.data } : {}),
    ...(selectedSpecId ? { selectedSpecId } : {}),
  }), [route.data, route.state.state, selectedSpecId])

  const specializationOptions = route.data ? flattenSpecs(route.data.classOptions) : []
  const specializationLabels = specializationOptions.map(({ classItem, spec }) => (
    spec.title || `${spec.specName || spec.name}${classItem.name}`
  ))
  const selectedIndex = Math.max(0, specializationOptions.findIndex(({ spec }) => (
    spec.id === model.selection?.specId || spec.specId === model.selection?.specId
  )))

  const openEvidence = (item: BuildEvidenceItem) => {
    const id = item.id as BuildsHomeEvidenceId
    const path = evidenceRoutes[id]
    const spec = model.selection?.specId
    void wowApi.analytics.track('builds_query_open', {
      queryKey: id,
      ...(spec ? { specId: spec } : {}),
    }, 'pages/builds/builds')
    navigateTo(path, {
      ...(id === 'tasks' ? {} : { spec }),
      ...(id === 'gear' ? { query: 'gear' } : {}),
      ...(id === 'simc' || id === 'tasks' ? { from: 'builds' } : {}),
    })
  }

  const openWorkflow = (stage: BuildWorkflowStage) => {
    if (stage.id === 'input') {
      const firstInput = model.evidenceItems.find((item) => item.id === 'talents' || item.id === 'gear')
      if (firstInput) openEvidence(firstInput)
      return
    }
    const evidence = model.evidenceItems.find((item) => item.id === (stage.id === 'validation' ? 'simc' : 'tasks'))
    if (evidence) openEvidence(evidence)
  }

  const useWorkspaceAction = () => {
    if (model.workspace.actionMode === 'retry') {
      void route.load()
      return
    }
    navigateTo('/pages/builds/workbench', { spec: model.selection?.specId })
  }

  return (
    <AppShell
      surfaceSlotId="asset_slot.builds-surface-texture"
      tabRoot
    >
      <PageFrame
        region="builds-home_target_region_page-header"
        sourceLabel={model.headerSourceLabel}
        title={model.title}
        variant="builds-home"
      >
        <RouteGrid
          className={styles['surface'] ?? ''}
          data-owner="builds-home-surface"
          data-refreshing={model.refreshing ? 'true' : 'false'}
          data-state={model.healthState}
        >
          <Picker
            className={styles['overviewRegion'] ?? ''}
            disabled={specializationOptions.length === 0 || model.initialLoading}
            mode="selector"
            range={specializationLabels}
            value={selectedIndex}
            onChange={(event) => {
              const selected = specializationOptions[Number(event.detail.value)]?.spec
              const nextId = selected?.id || selected?.specId
              if (nextId) setSelectedSpecId(nextId)
            }}
          >
            <BuildSpecializationOverview
              description={model.specialization.description}
              identity={model.specialization.identity}
              loading={model.initialLoading}
              sourceLabel={model.specialization.sourceLabel}
              state={model.specialization.state}
              stateLabel={model.specialization.stateLabel}
              title={model.specialization.title}
              onSelect={() => undefined}
            />
          </Picker>
          <RouteRegion className={styles['gridRegion'] ?? ''} data-region="specialization_grid">
            <BuildEvidenceNavigator
              items={model.evidenceItems}
              loading={model.initialLoading}
              variant="grid"
              onSelect={openEvidence}
            />
          </RouteRegion>
          <RouteRegion className={styles['workspaceRegion'] ?? ''} data-region="workspace_entry">
            <BuildWorkspaceEntry
              actionLabel={model.workspace.actionLabel}
              detail={model.workspace.detail}
              disabled={model.workspace.disabled}
              loading={model.initialLoading}
              state={model.workspace.state}
              statusLabel={model.workspace.statusLabel}
              summary={model.workspace.summary}
              title={model.workspace.title}
              onEnter={useWorkspaceAction}
            />
          </RouteRegion>
          <RouteRegion className={styles['listRegion'] ?? ''} data-region="build_list">
            <BuildEvidenceNavigator
              items={model.evidenceItems}
              loading={model.initialLoading}
              variant="list"
              onSelect={openEvidence}
            />
          </RouteRegion>
          <RouteRegion className={styles['workflowRegion'] ?? ''} data-region="workflow_guidance">
            <BuildWorkflowTimeline
              loading={model.initialLoading}
              stages={model.workflow}
              onSelect={openWorkflow}
            />
          </RouteRegion>
        </RouteGrid>
      </PageFrame>
    </AppShell>
  )
}
