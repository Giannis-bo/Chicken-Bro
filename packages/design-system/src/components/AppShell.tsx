import { View } from '@tarojs/components'
import type { CSSProperties, ReactNode } from 'react'

import {
  assetRuntimePath,
  type AssetSlotId,
  type ProductionAssetId,
} from '@wow-mini/assets-manifest'

import { runtimeSafeAreaStyle } from '../runtime-safe-area'
import { ownerClass, ownerStyle } from './style'

export interface AppShellProps {
  children: ReactNode
  tabRoot?: boolean
  dock?: ReactNode | undefined
  dockVariant?: 'plain' | 'safeAction' | undefined
  surfaceAssetId?: ProductionAssetId | undefined
  surfaceMaterialFamily?: 'default' | 'build-workspace' | undefined
  surfaceSlotId?: AssetSlotId | undefined
  surfaceMode?: 'tile' | 'cover' | undefined
}

export function AppShell({
  children,
  tabRoot = false,
  dock,
  dockVariant = 'plain',
  surfaceAssetId,
  surfaceMaterialFamily = 'default',
  surfaceSlotId,
  surfaceMode = 'tile',
}: AppShellProps) {
  const surfacePath = surfaceAssetId ? assetRuntimePath(surfaceAssetId) : null
  // Tab roots are one product surface. Route-owned art remains valid metadata,
  // but must not change the shared chrome when the user switches tabs.
  const appliedSurfacePath = tabRoot ? null : surfacePath
  const shellStyle = {
    ...runtimeSafeAreaStyle(),
    height: '100vh',
    overflow: 'hidden',
    ...(appliedSurfacePath ? {
      backgroundImage: `url(${appliedSurfacePath})`,
      backgroundPosition: 'center top',
      backgroundRepeat: surfaceMode === 'cover' ? 'no-repeat' : 'repeat',
      backgroundSize: surfaceMode === 'cover' ? 'cover' : '256px 256px',
    } : {}),
  } as CSSProperties

  return (
    <View
      className={ownerClass(
        'wow-theme',
        ownerStyle('shell'),
        tabRoot && ownerStyle('shellTabRoot'),
        Boolean(dock) && ownerStyle('shellWithDock'),
        surfaceMaterialFamily === 'build-workspace' && ownerStyle('shellBuildWorkspaceMaterial'),
      )}
      {...(surfaceAssetId ? {
        'data-asset-fallback': surfacePath ? 'false' : 'true',
        'data-asset-id': surfaceAssetId,
        'data-asset-missing': surfacePath ? 'false' : 'true',
        'data-surface-asset-id': surfaceAssetId,
      } : {})}
      data-role="app-mobile-stage"
      data-layout-mode={tabRoot ? 'tab-root' : 'pushed'}
      data-surface-material-family={surfaceMaterialFamily}
      {...(surfaceSlotId ? { 'data-slot-id': surfaceSlotId, 'data-surface-slot-id': surfaceSlotId } : {})}
      style={shellStyle}
    >
      <View
        className={ownerStyle('shellBody')}
      >
        {children}
      </View>
      {dock ? (
        <View
          className={ownerClass(
            ownerStyle('shellDock'),
            !tabRoot && ownerStyle('shellDockPushed'),
            dockVariant === 'safeAction' && ownerStyle('safeActionDock'),
          )}
        >
          {dock}
        </View>
      ) : null}
    </View>
  )
}
