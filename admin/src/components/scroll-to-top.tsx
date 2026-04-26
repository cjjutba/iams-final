import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/**
 * Resets scroll position to (0, 0) on every pathname change so that a route
 * transition always lands the user at the top of the new page.
 *
 * Mounted once inside <BrowserRouter> in App.tsx. Renders nothing.
 *
 * Skips:
 *   - hash-only navigations (#anchor) so in-page anchor links keep working
 *   - search-param-only changes (e.g. ?tab=...) so tabbed UI on the same
 *     page doesn't yank the user to the top mid-interaction
 */
export function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) return
    // Reset both the document scroll (the usual case) and any element that
    // happens to be the scrolling container when full-height layouts are
    // used. Using 'auto' (instant) instead of 'smooth' so the new page
    // appears at the top without a visible scroll animation on each nav.
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }, [pathname, hash])

  return null
}
