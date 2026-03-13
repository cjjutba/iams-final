import { useCallback, useEffect, useState } from 'react'
import { Cpu, Info } from 'lucide-react'

import { StatCard } from '@/components/charts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { edgeService } from '@/services/edge.service'

interface EdgeStatus {
  connected_devices: number
  total_devices: number
  queue_depth: number
  devices?: Array<{
    id: string
    name: string
    status: string
    last_heartbeat: string
    queue_size: number
  }>
}

export default function EdgeDevicesPage() {
  const [status, setStatus] = useState<EdgeStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await edgeService.getStatus()
      setStatus(data)
    } catch {
      setError('Edge device monitoring is not available yet.')
      setStatus(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStatus()
  }, [fetchStatus])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Edge Device Monitoring</h1>
        <p className="text-muted-foreground mt-1">
          Monitor connected Raspberry Pi edge devices
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Connected Devices"
          value={status?.connected_devices ?? 0}
          icon={Cpu}
        />
        <StatCard
          title="Total Devices"
          value={status?.total_devices ?? 0}
          icon={Cpu}
        />
        <StatCard
          title="Queue Depth"
          value={status?.queue_depth ?? 0}
          icon={Cpu}
        />
      </div>

      {(error || (!isLoading && !status)) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="h-5 w-5 text-muted-foreground" />
              Edge Devices Not Configured
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Edge device monitoring requires heartbeat reporting from connected
              Raspberry Pi devices. Once heartbeats are configured, device status
              will appear here.
            </p>
            <Button variant="outline" onClick={fetchStatus}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
