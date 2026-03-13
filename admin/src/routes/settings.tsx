import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Save } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { settingsService } from '@/services/settings.service'

const DEFAULT_SETTINGS: Record<string, string> = {
  current_semester: '1st',
  academic_year: '2025-2026',
  scan_interval: '60',
  early_leave_threshold: '3',
  cosine_similarity_threshold: '0.6',
  grace_period: '5',
  maintenance_mode: 'false',
}

export default function SettingsPage() {
  const [values, setValues] = useState<Record<string, string>>(DEFAULT_SETTINGS)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  const fetchSettings = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await settingsService.getAll()
      // API returns { key: { value, updated_at } }
      const loaded: Record<string, string> = { ...DEFAULT_SETTINGS }
      if (data && typeof data === 'object') {
        for (const [key, entry] of Object.entries(data)) {
          const val = (entry as { value?: string })?.value
          if (val !== undefined) {
            loaded[key] = String(val)
          }
        }
      }
      setValues(loaded)
    } catch {
      // Use defaults if settings endpoint is not available
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchSettings()
  }, [fetchSettings])

  const handleChange = (key: string, value: string) => {
    setValues(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await settingsService.update(values)
      toast.success('Settings saved successfully.')
    } catch {
      toast.error('Failed to save settings.')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">System Settings</h1>
          <p className="text-muted-foreground mt-1">Loading settings...</p>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={`settings-skeleton-${String(i)}`} className="h-48 w-full" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">System Settings</h1>
          <p className="text-muted-foreground mt-1">
            Configure system-wide settings
          </p>
        </div>
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="mr-2 h-4 w-4" />
          {isSaving ? 'Saving...' : 'Save Settings'}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Semester Configuration</CardTitle>
          <CardDescription>
            Set the current academic semester and year
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="current_semester">Current Semester</Label>
              <Input
                id="current_semester"
                value={values.current_semester}
                onChange={e => handleChange('current_semester', e.target.value)}
                placeholder="e.g. 1st"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="academic_year">Academic Year</Label>
              <Input
                id="academic_year"
                value={values.academic_year}
                onChange={e => handleChange('academic_year', e.target.value)}
                placeholder="e.g. 2025-2026"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recognition Thresholds</CardTitle>
          <CardDescription>
            Configure face recognition and presence tracking parameters
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="scan_interval">Scan Interval (seconds)</Label>
              <Input
                id="scan_interval"
                type="number"
                value={values.scan_interval}
                onChange={e => handleChange('scan_interval', e.target.value)}
                placeholder="60"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="early_leave_threshold">
                Early Leave Threshold (missed scans)
              </Label>
              <Input
                id="early_leave_threshold"
                type="number"
                value={values.early_leave_threshold}
                onChange={e => handleChange('early_leave_threshold', e.target.value)}
                placeholder="3"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cosine_similarity_threshold">
                Cosine Similarity Threshold
              </Label>
              <Input
                id="cosine_similarity_threshold"
                type="number"
                step="0.01"
                value={values.cosine_similarity_threshold}
                onChange={e => handleChange('cosine_similarity_threshold', e.target.value)}
                placeholder="0.6"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="grace_period">Grace Period (minutes)</Label>
              <Input
                id="grace_period"
                type="number"
                value={values.grace_period}
                onChange={e => handleChange('grace_period', e.target.value)}
                placeholder="5"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>System</CardTitle>
          <CardDescription>
            System-level configuration options
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="maintenance_mode">Maintenance Mode</Label>
              <p className="text-sm text-muted-foreground">
                When enabled, the system will reject new attendance submissions
              </p>
            </div>
            <Switch
              id="maintenance_mode"
              checked={values.maintenance_mode === 'true'}
              onCheckedChange={checked =>
                handleChange('maintenance_mode', String(checked))
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
