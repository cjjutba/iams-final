import { useEffect, useState } from "react"

/**
 * Returns `value` after it has been stable for `delayMs` milliseconds.
 *
 * Use for search inputs so each keystroke does not immediately drive
 * downstream filtering / network calls. The local input stays
 * responsive; only the debounced value is what consumers should react
 * to.
 *
 * Example:
 *   const [query, setQuery] = useState("")
 *   const debouncedQuery = useDebouncedValue(query, 300)
 *   const filtered = useMemo(() => filter(rows, debouncedQuery), [rows, debouncedQuery])
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])

  return debounced
}
