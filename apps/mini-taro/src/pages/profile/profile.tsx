import Taro, { useDidShow } from '@tarojs/taro'
import { useEffect, useRef, useState } from 'react'

import { wowApi } from '@wow-mini/api-client'
import { AppShell } from '@wow-mini/design-system/components/AppShell'
import { PageFrame } from '@wow-mini/design-system/components/PageFrame'
import { RouteStage } from '@wow-mini/design-system/components/RouteStage'
import { RouteRegion } from '@wow-mini/design-system/components/RouteFlow'
import {
  ProfileRecentSaves,
  ProfileSettingsList,
  ProfileSummaryPanel,
  ProfileTemplateLibrary,
} from '@wow-mini/design-system/components/ProfileTemplatesComponents'
import type { AuthUser, BuildTemplate } from '@wow-mini/domain'

import { navigateTo, useAsyncRoute } from '../_shared/route-runtime'
import {
  buildProfileTemplatesView,
  type ProfileTemplatesRouteState,
} from './profile-templates-model'
import styles from './profile.module.scss'

interface ProfilePayload {
  user: AuthUser
  templates: readonly BuildTemplate[]
}

interface EditableModalResult {
  confirm: boolean
  content?: string
}

const showEditableModal = Taro.showModal as unknown as (options: {
  title: string
  content: string
  editable: boolean
  placeholderText: string
  confirmText: string
}) => Promise<EditableModalResult>

function modelRouteState(state: string): ProfileTemplatesRouteState {
  if (state === 'loading') return 'loading'
  if (state === 'ready' || state === 'partial' || state === 'source_reference') return 'ready'
  if (state === 'stale') return 'stale'
  return 'blocked'
}

export default function ProfilePage() {
  const resumed = useRef(false)
  const [user, setUser] = useState<AuthUser>(() => wowApi.auth.profile())
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState('')
  const route = useAsyncRoute<ProfilePayload>(async () => {
    const localUser = wowApi.auth.profile()
    const templates = await wowApi.templates.fetch()
    return {
      payload: { user: localUser, templates: templates.payload.templates },
      fromFallback: templates.fromFallback,
      error: templates.error,
    }
  }, { fallbackPolicy: 'stale' })

  useEffect(() => {
    if (route.data?.user) setUser(route.data.user)
  }, [route.data])

  useDidShow(() => {
    if (!resumed.current) {
      resumed.current = true
      return
    }
    void route.load()
  })

  const saveProfile = async (patch: AuthUser) => {
    if (saving) return
    setSaving(true)
    try {
      const result = await wowApi.auth.saveProfileDraft({ ...user, ...patch })
      setUser(result.payload)
      await Taro.showToast({
        title: result.fromFallback ? '已保存到本机' : '已同步账户',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  const editAvatar = async (avatarUrl: string) => {
    if (!avatarUrl) {
      await Taro.showToast({ title: '未选择头像', icon: 'none' })
      return
    }
    await saveProfile({ avatarUrl })
  }

  const editProfile = async () => {
    if (saving) return
    try {
      const result = await showEditableModal({
        title: '编辑昵称',
        content: typeof user.nickname === 'string' ? user.nickname : '',
        editable: true,
        placeholderText: '输入昵称',
        confirmText: '保存',
      })
      const nickname = result.content?.trim().slice(0, 24) ?? ''
      if (result.confirm && nickname) await saveProfile({ nickname })
    } catch {
      // Closing the nickname editor is a normal no-op.
    }
  }

  const templates = route.data?.templates ?? wowApi.templates.list()
  const view = buildProfileTemplatesView(user, templates, modelRouteState(route.state.state))

  const deleteTemplate = async (id: string) => {
    const template = templates.find((item) => item.id === id)
    if (!template || deletingId) return
    const confirmation = await Taro.showModal({ title: '删除模板', content: `确定删除“${template.title}”吗？` })
    if (!confirmation.confirm) return
    setDeletingId(id)
    try {
      const result = await wowApi.templates.delete(id)
      await Taro.showToast({ title: result.fromFallback ? '已从本机删除' : '已删除并同步', icon: 'none' })
      await route.load()
    } finally {
      setDeletingId('')
    }
  }

  const showAllTemplates = async () => {
    const content = templates.length
      ? templates.slice(0, 10).map((template, index) => `${index + 1}. ${template.title}（${template.remote ? '账户' : '本地'}）`).join('\n')
      : '当前仓库没有返回模板'
    await Taro.showModal({ title: `全部模板 · ${templates.length}`, content: content.slice(0, 900), showCancel: false })
  }

  const openSetting = async (id: 'character' | 'preference' | 'source' | 'help') => {
    if (id === 'source') {
      await route.load()
      await Taro.showToast({ title: '已刷新资料来源', icon: 'none' })
      return
    }
    const item = view.settings.find((setting) => setting.id === id)
    const details = id === 'help'
      ? '资料与模板采用本地优先策略；远端不可用时会明确显示本地或陈旧状态，不会伪造账户同步。'
      : `${item?.label ?? '资料'}：${item?.value ?? '未设置'}\n当前版本仅展示已返回资料，尚无独立编辑端点。`
    await Taro.showModal({ title: item?.label ?? '帮助与反馈', content: details, showCancel: false })
  }

  return (
    <AppShell
      surfaceAssetId="builds-surface-texture.default"
      surfaceMode="tile"
      surfaceSlotId="asset_slot.profile-page-frame"
      tabRoot
    >
      <RouteStage className={styles['pageFrame'] ?? ''} routeState={route.state.state} targetRegionCount={7} width="full">
        <PageFrame region="page_header" title="我的" variant="profile">
          <RouteRegion className={styles['summaryRegion'] ?? ''}>
            <ProfileSummaryPanel
              avatarUrl={view.avatarUrl}
              metrics={view.metrics}
              nickname={saving ? '正在保存资料' : view.nickname}
              signature={view.signature}
              storageMode={view.storageMode}
              storageModeLabel={view.storageModeLabel}
              syncLabel={view.syncLabel}
              onAvatarEdit={(avatarUrl) => void editAvatar(avatarUrl)}
              onEdit={() => void editProfile()}
            />
          </RouteRegion>
          <RouteRegion className={styles['libraryRegion'] ?? ''}>
            <ProfileTemplateLibrary
              items={view.categories}
              onSelect={(id) => navigateTo(
                id === 'talent' ? '/pages/builds/talent-simulator' : '/pages/builds/detail',
                id === 'talent' ? { from: 'profile' } : { from: 'profile', query: 'gear' },
              )}
            />
          </RouteRegion>
          <RouteRegion className={styles['recentRegion'] ?? ''}>
            <ProfileRecentSaves
              deletingId={deletingId}
              items={view.recent}
              onDelete={(id) => void deleteTemplate(id)}
              onShowAll={() => void showAllTemplates()}
            />
          </RouteRegion>
          <RouteRegion className={styles['settingsRegion'] ?? ''}>
            <ProfileSettingsList items={view.settings} onSelect={(id) => void openSetting(id)} />
          </RouteRegion>
        </PageFrame>
      </RouteStage>
    </AppShell>
  )
}
