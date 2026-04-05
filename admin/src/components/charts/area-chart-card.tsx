import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const DEFAULT_COLORS = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
]

interface AreaSeries {
  key: string
  color?: string
  label?: string
}

interface AreaChartCardProps {
  title: string
  description?: string
  data: Record<string, unknown>[]
  xKey: string
  areas: AreaSeries[]
  height?: number
}

export function AreaChartCard({
  title,
  description,
  data,
  xKey,
  areas,
  height = 300,
}: AreaChartCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} fontSize={12} tickLine={false} axisLine={false} />
            <YAxis fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip />
            <Legend />
            {areas.map((area, index) => {
              const color = area.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length]
              return (
                <Area
                  key={area.key}
                  type="monotone"
                  dataKey={area.key}
                  name={area.label ?? area.key}
                  stroke={color}
                  fill={color}
                  fillOpacity={0.2}
                  strokeWidth={2}
                />
              )
            })}
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
