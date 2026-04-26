import { useCallback, useEffect, useState, type RefObject } from 'react'
import { Maximize, Minimize } from 'lucide-react'

interface Props {
  targetRef: RefObject<HTMLElement | null>
}

export function VideoFullscreenButton({ targetRef }: Props) {
  const [isFullscreen, setIsFullscreen] = useState(
    () => typeof document !== 'undefined' && !!document.fullscreenElement,
  )

  useEffect(() => {
    const sync = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [])

  const toggle = useCallback(async () => {
    const el = targetRef.current
    if (!el) return
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      } else {
        await el.requestFullscreen()
      }
    } catch (err) {
      console.warn('[fullscreen] toggle failed', err)
    }
  }, [targetRef])

  if (typeof document !== 'undefined' && !document.fullscreenEnabled) return null

  const Icon = isFullscreen ? Minimize : Maximize
  const label = isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="pointer-events-auto absolute bottom-3 right-3 z-20 inline-flex h-9 w-9 items-center justify-center rounded-md border border-white/15 bg-black/55 text-white opacity-0 backdrop-blur-sm transition-opacity duration-150 hover:bg-black/70 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 group-hover:opacity-100"
    >
      <Icon className="h-4 w-4" />
    </button>
  )
}
