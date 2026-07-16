import type { AuthUser, BuildTemplate } from '@wow-mini/domain'

export type ProfileTemplatesRouteState = 'loading' | 'ready' | 'stale' | 'blocked'
export type ProfileStorageMode = 'local' | 'mixed' | 'account'

export interface ProfileMetricView {
  id: 'talent' | 'gear' | 'archive'
  label: string
  value: string
}

export interface ProfileCategoryView {
  id: 'talent' | 'gear'
  title: string
  description: string
  count: number
}

export interface ProfileRecentTemplateView {
  position: number
  id: string
  title: string
  type: 'talent' | 'gear' | 'unavailable'
  typeLabel: string
  savedLabel: string
  sourceLabel: string
  deletable: boolean
  empty: boolean
}

export interface ProfileSettingView {
  id: 'character' | 'preference' | 'source' | 'help'
  label: string
  value: string
}

export interface ProfileTemplatesView {
  nickname: string
  signature: string
  avatarUrl: string
  storageMode: ProfileStorageMode
  storageModeLabel: string
  syncLabel: string
  metrics: readonly ProfileMetricView[]
  categories: readonly ProfileCategoryView[]
  recent: readonly [ProfileRecentTemplateView, ProfileRecentTemplateView]
  settings: readonly ProfileSettingView[]
}

function text(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return ''
}

function firstText(...values: readonly unknown[]): string {
  for (const value of values) {
    const candidate = text(value)
    if (candidate) return candidate
  }
  return ''
}

function bounded(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

function timestamp(template: BuildTemplate): number {
  const value = Date.parse(template.updatedAt || template.createdAt)
  return Number.isFinite(value) ? value : 0
}

function savedLabel(template: BuildTemplate): string {
  const source = template.updatedAt || template.createdAt
  if (!source || !Number.isFinite(Date.parse(source))) return '保存时间未返回'
  return `保存 ${source.replace('T', ' ').replace(/Z$/, '').slice(0, 16)}`
}

function recentPosition(template: BuildTemplate | undefined, position: number): ProfileRecentTemplateView {
  if (!template) {
    const type = position === 0 ? 'talent' : 'gear'
    return {
      position,
      id: '',
      title: type === 'talent' ? '暂无天赋保存' : '暂无装备保存',
      type,
      typeLabel: type === 'talent' ? '天赋模板' : '装备模板',
      savedLabel: '保存时间未返回',
      sourceLabel: '等待创建',
      deletable: false,
      empty: true,
    }
  }
  return {
    position,
    id: template.id,
    title: bounded(template.title || (template.type === 'talent' ? '天赋模板' : '装备模板'), 34),
    type: template.type,
    typeLabel: template.type === 'talent' ? '天赋模板' : '装备模板',
    savedLabel: savedLabel(template),
    sourceLabel: template.remote ? '账户模板' : '本地模板',
    deletable: Boolean(template.id),
    empty: false,
  }
}

function storageMode(user: AuthUser, templates: readonly BuildTemplate[], routeState: ProfileTemplatesRouteState): ProfileStorageMode {
  const remoteCount = templates.filter((template) => template.remote).length
  const localCount = templates.length - remoteCount
  if (routeState === 'ready' && user.openid && remoteCount > 0 && localCount === 0) return 'account'
  if (remoteCount > 0 && localCount > 0) return 'mixed'
  if (routeState === 'ready' && user.openid && templates.length === 0) return 'account'
  return 'local'
}

export function buildProfileTemplatesView(
  user: AuthUser,
  templates: readonly BuildTemplate[],
  routeState: ProfileTemplatesRouteState,
): ProfileTemplatesView {
  const ordered = [...templates].sort((left, right) => timestamp(right) - timestamp(left))
  const talentCount = ordered.filter((template) => template.type === 'talent').length
  const gearCount = ordered.filter((template) => template.type === 'gear').length
  const mode = storageMode(user, ordered, routeState)
  const modeLabels: Readonly<Record<ProfileStorageMode, string>> = {
    local: '本地模式',
    mixed: '本地与账户',
    account: '账户同步',
  }
  const character = [
    firstText(user['characterName'], user['character']),
    firstText(user['realmName'], user['realm'], user['serverName']),
  ].filter(Boolean).join(' · ')
  const preference = [
    firstText(user['className'], user['classLabel']),
    firstText(user['specName'], user['specializationName']),
  ].filter(Boolean).join(' · ')
  const syncLabel = routeState === 'loading'
    ? '正在读取模板'
    : routeState === 'stale'
      ? '远端不可用，使用本地资料'
      : routeState === 'blocked'
        ? '资料同步不可用'
        : mode === 'account'
          ? '账户资料已返回'
          : mode === 'mixed'
            ? '本地与账户模板已合并'
            : '使用本地资料'

  return {
    nickname: bounded(firstText(user.nickname) || '点击设置昵称', 24),
    signature: bounded(firstText(user['signature'], user['bio']) || '未设置个性签名', 54),
    avatarUrl: text(user.avatarUrl),
    storageMode: mode,
    storageModeLabel: modeLabels[mode],
    syncLabel,
    metrics: [
      { id: 'talent', label: '天赋模板', value: String(talentCount) },
      { id: 'gear', label: '装备模板', value: String(gearCount) },
      { id: 'archive', label: '档案状态', value: ordered.length ? `已创建 ${ordered.length}` : '尚未创建' },
    ],
    categories: [
      { id: 'talent', title: '天赋模板', description: '创建与管理天赋方案', count: talentCount },
      { id: 'gear', title: '装备模板', description: '搭配与管理装备方案', count: gearCount },
    ],
    recent: [recentPosition(ordered[0], 0), recentPosition(ordered[1], 1)],
    settings: [
      { id: 'character', label: '角色与服务器', value: bounded(character || '未设置', 28) },
      { id: 'preference', label: '职业偏好', value: bounded(preference || '未设置', 28) },
      { id: 'source', label: '数据源设置', value: modeLabels[mode] },
      { id: 'help', label: '帮助与反馈', value: '使用说明' },
    ],
  }
}
