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

export type PageChromeMode = 'root' | 'pushed' | 'pushed-action'
export type PageFrameRightActionLayout = 'default' | 'builds-class-selector' | 'captain-chat'

const PAGE_FRAME_RIGHT_ACTION_WIDTHS: Readonly<Record<PageFrameRightActionLayout, number>> = {
  default: 36,
  'builds-class-selector': 120,
  'captain-chat': 80,
}

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
  return 'pushed'
}

export function resolvePageFrameRightActionLayout(
  variant: PageFrameVariant,
  requestedLayout: PageFrameRightActionLayout = 'default',
): PageFrameRightActionLayout {
  return variant === 'simulator-home' ? 'captain-chat' : requestedLayout
}

export function resolvePageFrameRightActionWidth(
  layout: PageFrameRightActionLayout = 'default',
): number {
  return PAGE_FRAME_RIGHT_ACTION_WIDTHS[layout]
}
