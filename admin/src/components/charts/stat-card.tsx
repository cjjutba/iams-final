import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon: LucideIcon
  trend?: { value: number; label: string }
}

export function StatCard({ title, value, description, icon: Icon, trend }: StatCardProps) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border bg-card px-5 py-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground tracking-wide uppercase">{title}</span>
        <Icon className="h-4 w-4 text-muted-foreground/60" />
      </div>
      <div className="text-2xl font-semibold tracking-tight">{value}</div>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      {trend && (
        <p className={`text-xs ${trend.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}
        </p>
      )}
    </div>
  )
}
