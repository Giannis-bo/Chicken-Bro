import styles from './reconstruction.module.scss'
import { styleSelectorClass } from './selector-markers'

export function reconstructionStyle(name: string): string {
  return [styles[name] ?? '', styleSelectorClass(name)].filter(Boolean).join(' ')
}

export function reconstructionClass(
  ...values: readonly (string | false | null | undefined)[]
): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}
