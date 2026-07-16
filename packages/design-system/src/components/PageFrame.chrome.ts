export type PageFrameVariant =
  | 'default'
  | 'news-home'
  | 'builds-home'
  | 'workbench'
  | 'news-list'
  | 'news-detail'
  | 'build-intel'
  | 'talent-simulator'
  | 'gear-detail'
  | 'simulator-home'
  | 'simc-submit'
  | 'chickenbro-chat'
  | 'tasks-list'
  | 'task-detail'
  | 'profile'

export type PageChromeMode = 'root' | 'pushed' | 'pushed-action' | 'chat'

const ROOT_PAGE_VARIANTS = new Set<PageFrameVariant>([
  'news-home',
  'builds-home',
  'simulator-home',
  'profile',
])

export function resolvePageChromeMode(
  variant: PageFrameVariant,
  onBack?: (() => void) | undefined,
): PageChromeMode {
  if (ROOT_PAGE_VARIANTS.has(variant)) return 'root'
  const pushed = variant === 'workbench' || Boolean(onBack)
  if (!pushed) return 'root'
  if (variant === 'build-intel' || variant === 'simc-submit') return 'pushed-action'
  if (variant === 'chickenbro-chat') return 'chat'
  return 'pushed'
}
