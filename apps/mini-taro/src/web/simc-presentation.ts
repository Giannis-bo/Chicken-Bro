export { simcStatuses, simcFightStyles, simcLabel, simcMetricName, simcResourceName, simcSpellName } from '../features/simc/simc-terms'

export function simcNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? '未记录' : value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

export function simcAttributeValue(name: string, value: number): string {
  return `${simcNumber(value)}${name.endsWith('_pct') ? '%' : ''}`
}

export function simcDate(value: string): string {
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date) : '时间未记录'
}
