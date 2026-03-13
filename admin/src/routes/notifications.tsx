import { useState, useEffect, useCallback } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Send, CheckCircle } from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { notificationsService } from '@/services/notifications.service'
import type { Notification, BroadcastNotificationRequest } from '@/types'

const broadcastSchema = z.object({
  target: z.enum(['all', 'students', 'faculty']),
  title: z.string().min(1, 'Title is required'),
  message: z.string().min(1, 'Message is required'),
})

type BroadcastForm = z.infer<typeof broadcastSchema>

function SendNotificationForm() {
  const [sending, setSending] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<BroadcastForm>({
    resolver: zodResolver(broadcastSchema),
    defaultValues: { target: 'all', title: '', message: '' },
  })

  const targetValue = watch('target')

  const onSubmit = async (data: BroadcastForm) => {
    setSending(true)
    try {
      const payload: BroadcastNotificationRequest = {
        target: data.target,
        title: data.title,
        message: data.message,
      }
      await notificationsService.broadcast(payload)
      toast.success('Notification sent successfully')
      reset()
    } catch {
      toast.error('Failed to send notification. The broadcast endpoint may not be available yet.')
    } finally {
      setSending(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Send Notification</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="target">Target</Label>
            <Select value={targetValue} onValueChange={(v) => setValue('target', v as BroadcastForm['target'])}>
              <SelectTrigger>
                <SelectValue placeholder="Select target" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Users</SelectItem>
                <SelectItem value="students">Students Only</SelectItem>
                <SelectItem value="faculty">Faculty Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" {...register('title')} placeholder="Notification title" />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="message">Message</Label>
            <Textarea id="message" {...register('message')} placeholder="Notification message" rows={4} />
            {errors.message && <p className="text-sm text-destructive">{errors.message.message}</p>}
          </div>

          <Button type="submit" disabled={sending}>
            <Send className="mr-2 h-4 w-4" />
            {sending ? 'Sending...' : 'Send Notification'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function MarkReadAction({ notification, onMarked }: { notification: Notification; onMarked: () => void }) {
  const [loading, setLoading] = useState(false)

  if (notification.read) {
    return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Read</Badge>
  }

  const handleMarkRead = async () => {
    setLoading(true)
    try {
      await notificationsService.markRead(notification.id)
      toast.success('Marked as read')
      onMarked()
    } catch {
      toast.error('Failed to mark as read')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={() => void handleMarkRead()} disabled={loading}>
      <CheckCircle className="mr-1 h-3 w-3" />
      Mark Read
    </Button>
  )
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)

  const fetchNotifications = useCallback(async () => {
    try {
      const data = await notificationsService.list()
      setNotifications(data)
    } catch {
      toast.error('Failed to load notifications')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchNotifications()
  }, [fetchNotifications])

  const columns: ColumnDef<Notification>[] = [
    {
      accessorKey: 'title',
      header: 'Title',
    },
    {
      accessorKey: 'message',
      header: 'Message',
      cell: ({ row }) => (
        <span className="max-w-[300px] truncate block" title={row.original.message}>
          {row.original.message}
        </span>
      ),
    },
    {
      accessorKey: 'type',
      header: 'Type',
      cell: ({ row }) => (
        <Badge variant="outline">{row.original.type}</Badge>
      ),
    },
    {
      accessorKey: 'read',
      header: 'Read',
      cell: ({ row }) => (
        <Badge className={row.original.read
          ? 'bg-green-100 text-green-800 hover:bg-green-100'
          : 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100'
        }>
          {row.original.read ? 'Read' : 'Unread'}
        </Badge>
      ),
    },
    {
      accessorKey: 'created_at',
      header: 'Created At',
      cell: ({ row }) => {
        try {
          return format(new Date(row.original.created_at), 'MMM d, yyyy h:mm a')
        } catch {
          return row.original.created_at
        }
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <MarkReadAction notification={row.original} onMarked={() => void fetchNotifications()} />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Notification Management</h1>
        <p className="text-muted-foreground">Send and manage system notifications</p>
      </div>

      <Tabs defaultValue="send">
        <TabsList>
          <TabsTrigger value="send">Send Notification</TabsTrigger>
          <TabsTrigger value="history">Notification History</TabsTrigger>
        </TabsList>

        <TabsContent value="send" className="mt-4">
          <SendNotificationForm />
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <DataTable
            columns={columns}
            data={notifications}
            isLoading={loading}
            searchPlaceholder="Search notifications..."
            searchColumn="title"
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
