import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Closes a surface (menu, dropdown) whenever the SPA route changes, so a
 * navigation from outside the surface — notification deep-link, command
 * palette — never leaves a stale panel hanging over new content.
 *
 * Render-time state adjustment per
 * https://react.dev/learn/you-might-not-need-an-effect — no setState inside
 * an effect, and no extra render pass beyond the route change itself.
 */
export function useCloseOnRouteChange(open: boolean, close: () => void) {
  const { pathname, search } = useLocation()
  const [prevRoute, setPrevRoute] = useState(pathname + search)
  const route = pathname + search
  if (prevRoute !== route) {
    setPrevRoute(route)
    if (open) close()
  }
}

/**
 * Outside-click + Escape + focus-out dismissal for an anchored panel.
 * Attach the returned ref to the wrapper that contains BOTH the trigger
 * and the panel. Pass `closeOnBlur: true` only for mouse-and-keyboard
 * surfaces whose panel contains no focusable elements of its own.
 */
export function useDismiss(
  ref: React.RefObject<HTMLElement | null>,
  open: boolean,
  close: () => void,
  closeOnBlur = false,
) {
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  if (!closeOnBlur) return {}

  return {
    onBlur: (e: React.FocusEvent) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) close()
    },
  }
}
