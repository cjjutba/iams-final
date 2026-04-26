import type { Table } from "@tanstack/react-table"
import { SearchIcon } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { Input } from "@/components/ui/input"

interface DataTableToolbarProps<TData> {
  table: Table<TData>
  /** Single-column filter mode — bound to a specific accessorKey. */
  searchColumn?: string
  /** Multi-field controlled search query (TanStack globalFilter). */
  globalFilter?: string
  onGlobalFilterChange?: (value: string) => void
  searchPlaceholder?: string
  /** Debounce delay before notifying the parent. Default 300ms. */
  searchDebounceMs?: number
  children?: React.ReactNode
}

export function DataTableToolbar<TData>({
  table,
  searchColumn,
  globalFilter,
  onGlobalFilterChange,
  searchPlaceholder = "Search...",
  searchDebounceMs = 300,
  children,
}: DataTableToolbarProps<TData>) {
  // Global filter takes precedence — when the consumer passes a setter
  // we drive the input from `globalFilter` regardless of `searchColumn`.
  const useGlobal = onGlobalFilterChange !== undefined
  const column = !useGlobal && searchColumn ? table.getColumn(searchColumn) : undefined

  const externalValue = useGlobal
    ? (globalFilter ?? "")
    : ((column?.getFilterValue() as string) ?? "")
  const disabled = !useGlobal && !column

  // Local input state so each keystroke renders instantly without
  // round-tripping through the parent's filter pipeline. The parent only
  // hears about it once typing has been still for `searchDebounceMs`.
  const [inputValue, setInputValue] = useState(externalValue)

  // External -> local sync: when the parent value changes from an
  // outside cause (e.g. "Clear filters", route mount with a stored
  // sessionStorage query) adopt it into the input. Done as a render-time
  // adjustment per the React docs ("you might not need an effect")
  // because the alternative — a useEffect that calls setInputValue — is
  // both flagged by react-hooks/set-state-in-effect and produces an
  // extra render after the prop change.
  const [lastExternal, setLastExternal] = useState(externalValue)
  if (externalValue !== lastExternal) {
    setLastExternal(externalValue)
    setInputValue(externalValue)
  }

  // Refs that always point at the latest values so the deferred timer
  // callback can read them without being captured by stale closures.
  // Without this, calling `notifyParent` from a `setTimeout` would use
  // whatever `onGlobalFilterChange` was at the time the timer was
  // *scheduled*, not at the time it *fires*. Updated in an effect (after
  // commit) rather than during render to satisfy `react-hooks/refs`;
  // this is fine in practice because the timer can only fire after at
  // least one paint cycle has elapsed.
  const externalValueRef = useRef(externalValue)
  const notifyParentRef = useRef<(next: string) => void>(() => {})

  useEffect(() => {
    externalValueRef.current = externalValue
    notifyParentRef.current = useGlobal
      ? (next: string) => onGlobalFilterChange!(next)
      : (next: string) => column?.setFilterValue(next)
  })

  // Imperative debounce: a single timer per pending notification. Each
  // keystroke clears the prior timer and schedules a fresh one. Compared
  // to a useEffect-driven debounce hook this collapses the propagation
  // chain into one notify + one parent render at the end of typing,
  // instead of one render to update the debounced value and another to
  // run the effect that notifies the parent — which the eye picks up as
  // "the table flickers a beat after I stop typing."
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleChange = useCallback(
    (next: string) => {
      setInputValue(next)
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = setTimeout(() => {
        debounceTimerRef.current = null
        if (next !== externalValueRef.current) {
          notifyParentRef.current(next)
        }
      }, searchDebounceMs)
    },
    [searchDebounceMs],
  )

  // Cancel any pending notification on unmount so consumers don't get a
  // stale state-update after the component is gone.
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
        debounceTimerRef.current = null
      }
    }
  }, [])

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <div className="relative flex-1 max-w-sm">
        <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder={searchPlaceholder}
          value={inputValue}
          onChange={(e) => handleChange(e.target.value)}
          className="pl-8"
          disabled={disabled}
        />
      </div>
      {children && (
        <div className="flex items-center gap-2">{children}</div>
      )}
    </div>
  )
}
