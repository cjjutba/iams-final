import type { Table } from "@tanstack/react-table"
import { SearchIcon } from "lucide-react"

import { Input } from "@/components/ui/input"

interface DataTableToolbarProps<TData> {
  table: Table<TData>
  /** Single-column filter mode — bound to a specific accessorKey. */
  searchColumn?: string
  /** Multi-field controlled search query (TanStack globalFilter). */
  globalFilter?: string
  onGlobalFilterChange?: (value: string) => void
  searchPlaceholder?: string
  children?: React.ReactNode
}

export function DataTableToolbar<TData>({
  table,
  searchColumn,
  globalFilter,
  onGlobalFilterChange,
  searchPlaceholder = "Search...",
  children,
}: DataTableToolbarProps<TData>) {
  // Global filter takes precedence — when the consumer passes a setter
  // we drive the input from `globalFilter` regardless of `searchColumn`.
  const useGlobal = onGlobalFilterChange !== undefined
  const column = !useGlobal && searchColumn ? table.getColumn(searchColumn) : undefined

  const value = useGlobal ? (globalFilter ?? "") : ((column?.getFilterValue() as string) ?? "")
  const onChange = useGlobal
    ? (next: string) => onGlobalFilterChange!(next)
    : (next: string) => column?.setFilterValue(next)
  const disabled = !useGlobal && !column

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <div className="relative flex-1 max-w-sm">
        <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder={searchPlaceholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
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
