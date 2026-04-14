import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Loader2, Save } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { useSettings, useUpdateSettings, useNotificationPreferences, useUpdateNotificationPreferences } from '@/hooks/use-queries'
import type { NotificationPreference } from '@/types'

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
  usePageTitle('Settings')
  const [values, setValues] = useState<Record<string, string>>(DEFAULT_SETTINGS)
  const { data: settingsData, isLoading } = useSettings()
  const updateSettings = useUpdateSettings()

  useEffect(() => {
    if (settingsData && typeof settingsData === 'object') {
      const loaded: Record<string, string> = { ...DEFAULT_SETTINGS }
      for (const [key, entry] of Object.entries(settingsData)) {
        const val = (entry as { value?: string })?.value
        if (val !== undefined) {
          loaded[key] = String(val)
        }
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setValues(loaded)
    }
  }, [settingsData])

  const handleChange = (key: string, value: string) => {
    setValues(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    try {
      await updateSettings.mutateAsync(values)
      toast.success('Settings saved successfully.')
    } catch {
      toast.error('Failed to save settings.')
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">System Settings</h1>
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
          <h1 className="text-2xl font-semibold">System Settings</h1>
          <p className="text-muted-foreground mt-1">
            Configure system-wide settings
          </p>
        </div>
        <Button onClick={() => void handleSave()} disabled={updateSettings.isPending}>
          {updateSettings.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Save Settings
            </>
          )}
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

      <NotificationPreferencesCard />
    </div>
  )
}

function NotificationPreferencesCard() {
  const { data: prefs, isLoading } = useNotificationPreferences()
  const updatePrefs = useUpdateNotificationPreferences()

  const handleToggle = (key: keyof NotificationPreference, checked: boolean) => {
    updatePrefs.mutate(
      { [key]: checked },
      {
        onError: () => toast.error('Failed to update preference'),
      },
    )
  }

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />
  }

  const items: { key: keyof NotificationPreference; label: string; description: string }[] = [
    { key: 'early_leave_alerts', label: 'Early Leave Alerts', description: 'Receive alerts when a student leaves class early' },
    { key: 'anomaly_alerts', label: 'Anomaly Alerts', description: 'Receive alerts for anomalous attendance patterns' },
    { key: 'attendance_confirmation', label: 'Attendance Confirmations', description: 'Receive confirmations when attendance is recorded' },
    { key: 'low_attendance_warning', label: 'Low Attendance Warnings', description: 'Receive warnings when attendance drops below threshold' },
    { key: 'daily_digest', label: 'Daily Digest', description: 'Receive a daily attendance summary at 8 PM' },
    { key: 'weekly_digest', label: 'Weekly Digest', description: 'Receive a weekly attendance summary on Mondays' },
    { key: 'email_enabled', label: 'Email Notifications', description: 'Also send notifications to your email address' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notification Preferences</CardTitle>
        <CardDescription>
          Control which notifications you receive
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        {items.map(({ key, label, description }) => (
          <div key={key} className="flex items-center justify-between py-3">
            <div className="space-y-0.5">
              <Label htmlFor={`pref-${key}`}>{label}</Label>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            <Switch
              id={`pref-${key}`}
              checked={prefs?.[key] as boolean ?? true}
              onCheckedChange={checked => handleToggle(key, checked)}
              disabled={updatePrefs.isPending}
            />
          </div>
        ))}
        <Separator className="my-3" />
        <div className="flex items-center justify-between py-3">
          <div className="space-y-0.5">
            <Label htmlFor="pref-threshold">Low Attendance Threshold (%)</Label>
            <p className="text-sm text-muted-foreground">
              Trigger warning when attendance drops below this percentage
            </p>
          </div>
          <Input
            id="pref-threshold"
            type="number"
            min={0}
            max={100}
            step={5}
            className="w-20"
            value={prefs?.low_attendance_threshold ?? 75}
            onChange={e => {
              const val = parseFloat(e.target.value)
              if (!isNaN(val)) {
                updatePrefs.mutate(
                  { low_attendance_threshold: val },
                  { onError: () => toast.error('Failed to update threshold') },
                )
              }
            }}
          />
        </div>
      </CardContent>
    </Card>
  )
}
