import type { Table } from "@tanstack/react-table"
import { SearchIcon } from "lucide-react"

import { Input } from "@/components/ui/input"

interface DataTableToolbarProps<TData> {
  table: Table<TData>
  searchColumn?: string
  searchPlaceholder?: string
  children?: React.ReactNode
}

export function DataTableToolbar<TData>({
  table,
  searchColumn,
  searchPlaceholder = "Search...",
  children,
}: DataTableToolbarProps<TData>) {
  const column = searchColumn ? table.getColumn(searchColumn) : undefined

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <div className="relative flex-1 max-w-sm">
        <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder={searchPlaceholder}
          value={(column?.getFilterValue() as string) ?? ""}
          onChange={(e) => column?.setFilterValue(e.target.value)}
          className="pl-8"
          disabled={!column}
        />
      </div>
      {children && (
        <div className="flex items-center gap-2">{children}</div>
      )}
    </div>
  )
}
