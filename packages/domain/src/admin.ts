export interface AdminAccess { isAdmin: boolean; accountId: string }
export interface AdminDaily { date: string; newUsers: number; activeUsers: number; questions: number; simulations: number }
export interface AdminOverview {
  start: string; end: string; timezone: 'Asia/Shanghai'; generatedAt: string; scope: 'current_qq_users'
  users: { total: number; new: number; active: number }
  chat: { total: number; succeeded: number; failed: number; running: number; successRate: number | null; resolved: number; unresolved: number; feedbackRate: number | null; resolutionRate: number | null; avgSeconds: number | null; p95Seconds: number | null }
  simc: { total: number; succeeded: number; failed: number; queued: number; running: number; cancelled: number; invalidResults: number; successRate: number | null; avgSeconds: number | null; p95Seconds: number | null }
  daily: AdminDaily[]
  specializations: Array<{ class: string; spec: string; count: number }>
}
const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const count = (v: unknown): v is number => Number.isSafeInteger(v) && typeof v === 'number' && v >= 0
const metric = (v: unknown): boolean => v === null || (typeof v === 'number' && Number.isFinite(v) && v >= 0)
const rate = (v: unknown): boolean => metric(v) && (v === null || (v as number) <= 1)
const date = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/u.test(v)
export function isAdminAccess(v: unknown): v is AdminAccess {
  return record(v) && typeof v['isAdmin'] === 'boolean' && typeof v['accountId'] === 'string' && /^[0-9a-f-]{36}$/u.test(v['accountId'])
}
export function isAdminOverview(v: unknown): v is AdminOverview {
  if (!record(v) || !date(v['start']) || !date(v['end']) || v['timezone'] !== 'Asia/Shanghai' || v['scope'] !== 'current_qq_users' || typeof v['generatedAt'] !== 'string' || !Number.isFinite(Date.parse(v['generatedAt']))) return false
  const u=v['users'], c=v['chat'], s=v['simc']
  return record(u) && ['total','new','active'].every(k=>count(u[k])) && record(c) && record(s)
    && ['total','succeeded','failed','running','resolved','unresolved'].every(k=>count(c[k]))
    && ['total','succeeded','failed','queued','running','cancelled','invalidResults'].every(k=>count(s[k]))
    && ['successRate','feedbackRate','resolutionRate'].every(k=>rate(c[k])) && rate(s['successRate'])
    && ['avgSeconds','p95Seconds'].every(k=>metric(c[k]) && metric(s[k]))
    && Array.isArray(v['daily']) && v['daily'].length <= 366 && v['daily'].every(d=>record(d) && date(d['date']) && ['newUsers','activeUsers','questions','simulations'].every(k=>count(d[k])))
    && Array.isArray(v['specializations']) && v['specializations'].every(d=>record(d) && typeof d['class']==='string' && typeof d['spec']==='string' && count(d['count']))
}
