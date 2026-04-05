import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useUpdateUser } from '@/hooks/use-queries'
import type { UserResponse } from '@/types'

const roleLabels: Record<string, string> = {
  student: 'Student',
  faculty: 'Faculty',
  admin: 'Admin',
}

interface EditUserDialogProps {
  user: UserResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditUserDialog({ user, open, onOpenChange }: EditUserDialogProps) {
  const updateUser = useUpdateUser()

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
  })

  useEffect(() => {
    if (open && user) {
      setForm({
        first_name: user.first_name,
        last_name: user.last_name,
        email: user.email,
        phone: user.phone ?? '',
      })
    }
  }, [open, user])

  function handleChange(field: string, value: string) {
    if (field === 'phone') {
      const digits = value.replace(/\D/g, '').slice(0, 11)
      setForm((prev) => ({ ...prev, [field]: digits }))
      return
    }
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!user) return

    if (!form.first_name || !form.last_name) {
      toast.error('First name and last name are required.')
      return
    }
    if (form.phone && form.phone.length !== 11) {
      toast.error('Phone number must be exactly 11 digits (e.g. 09xxxxxxxxx).')
      return
    }

    try {
      await updateUser.mutateAsync({
        id: user.id,
        data: {
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email || undefined,
          phone: form.phone || undefined,
        },
      })
      toast.success(`${form.first_name} ${form.last_name} has been updated.`)
      onOpenChange(false)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to update user'
      const errorMsg = typeof msg === 'string' ? msg : JSON.stringify(msg)
      toast.error(errorMsg)
    }
  }

  if (!user) return null

  const label = roleLabels[user.role] ?? 'User'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit {label}</DialogTitle>
          <DialogDescription>
            Update the details for {user.first_name} {user.last_name}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="edit_first_name">First Name *</Label>
              <Input
                id="edit_first_name"
                placeholder="Juan"
                value={form.first_name}
                onChange={(e) => handleChange('first_name', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit_last_name">Last Name *</Label>
              <Input
                id="edit_last_name"
                placeholder="Dela Cruz"
                value={form.last_name}
                onChange={(e) => handleChange('last_name', e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit_email">Email</Label>
            <Input
              id="edit_email"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(e) => handleChange('email', e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit_phone">Phone</Label>
            <Input
              id="edit_phone"
              type="tel"
              inputMode="numeric"
              maxLength={11}
              placeholder="09xxxxxxxxx"
              value={form.phone}
              onChange={(e) => handleChange('phone', e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={updateUser.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={updateUser.isPending}>
              {updateUser.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
