import { Button } from '@tarojs/components'
import type { ComponentProps } from 'react'

import { ownerClass, ownerStyle } from './style'

export type ControlButtonProps = ComponentProps<typeof Button>

/**
 * Behaviour owner for controls whose visual geometry is supplied by a complex
 * component. Standard product actions should use ActionButton instead.
 */
export function ControlButton({ className, hoverClass, ...props }: ControlButtonProps) {
  return (
    <Button
      {...props}
      className={ownerClass(ownerStyle('nativeControl'), className)}
      hoverClass={hoverClass ?? ownerStyle('nativeControlPressed')}
      hoverStayTime={props.hoverStayTime ?? 80}
    />
  )
}
