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
        if (val !== undefined && key in DEFAULT_SETTINGS) {
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
          <h1 className="text-2xl font-semibold">Settings</h1>
          <p className="text-muted-foreground mt-1">Loading settings...</p>
        </div>
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={`settings-skeleton-${String(i)}`} className="h-40 w-full" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Settings</h1>
          <p className="text-muted-foreground mt-1">
            Academic calendar and notification preferences
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
              Save
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
    { key: 'early_leave_alerts', label: 'Early Leave Alerts', description: 'Notify when a student leaves class early' },
    { key: 'low_attendance_warning', label: 'Low Attendance Warnings', description: 'Warn when attendance drops below the threshold' },
    { key: 'email_enabled', label: 'Email Notifications', description: 'Also deliver notifications to your email' },
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
