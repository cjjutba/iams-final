import { useState } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreateUser, useCreateStudentRecord } from '@/hooks/use-queries'
import type { UserRole } from '@/types'

interface CreateUserDialogProps {
  role: UserRole
  open: boolean
  onOpenChange: (open: boolean) => void
}

const roleLabels: Record<UserRole, string> = {
  student: 'Student',
  faculty: 'Faculty',
  admin: 'Admin',
}

export function CreateUserDialog({ role, open, onOpenChange }: CreateUserDialogProps) {
  const createUser = useCreateUser()
  const createStudentRecord = useCreateStudentRecord()
  const isPending = createUser.isPending || createStudentRecord.isPending

  const [form, setForm] = useState({
    first_name: '',
    middle_name: '',
    last_name: '',
    email: '',
    password: '',
    phone: '',
    student_id: '',
    course: '',
    year_level: '',
    section: '',
    birthdate: '',
    contact_number: '',
  })

  function resetForm() {
    setForm({
      first_name: '',
      middle_name: '',
      last_name: '',
      email: '',
      password: '',
      phone: '',
      student_id: '',
      course: '',
      year_level: '',
      section: '',
      birthdate: '',
      contact_number: '',
    })
  }

  function handleChange(field: string, value: string) {
    // Enforce digits-only and max 11 chars for phone fields
    if (field === 'phone' || field === 'contact_number') {
      const digits = value.replace(/\D/g, '').slice(0, 11)
      setForm((prev) => ({ ...prev, [field]: digits }))
      return
    }
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!form.first_name || !form.last_name) {
      toast.error('First name and last name are required.')
      return
    }

    try {
      if (role === 'student') {
        // Student: create student_records entry only (no auth account)
        if (!form.student_id) {
          toast.error('Student ID is required.')
          return
        }
        if (form.contact_number && form.contact_number.length !== 11) {
          toast.error('Contact number must be exactly 11 digits (e.g. 09xxxxxxxxx).')
          return
        }

        await createStudentRecord.mutateAsync({
          student_id: form.student_id,
          first_name: form.first_name,
          middle_name: form.middle_name || undefined,
          last_name: form.last_name,
          email: form.email || undefined,
          course: form.course || undefined,
          year_level: form.year_level ? Number(form.year_level) : undefined,
          section: form.section || undefined,
          birthdate: form.birthdate || undefined,
          contact_number: form.contact_number || undefined,
        })
      } else {
        // Faculty/Admin: create users table entry with auth
        if (!form.email || !form.password) {
          toast.error('Email and password are required.')
          return
        }
        if (form.password.length < 8) {
          toast.error('Password must be at least 8 characters.')
          return
        }
        if (form.phone && form.phone.length !== 11) {
          toast.error('Phone number must be exactly 11 digits (e.g. 09xxxxxxxxx).')
          return
        }

        await createUser.mutateAsync({
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          password: form.password,
          phone: form.phone || undefined,
          role,
        })
      }

      const successMsg = role === 'student'
        ? `Student record for ${form.first_name} ${form.last_name} created successfully.`
        : `${roleLabels[role]} account for ${form.first_name} ${form.last_name} created successfully.`
      toast.success(successMsg)
      resetForm()
      onOpenChange(false)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      const msg = e?.response?.data?.detail || e?.message || 'Failed to create record'
      const errorMsg = typeof msg === 'string' ? msg : JSON.stringify(msg)
      toast.error(errorMsg)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) resetForm()
        onOpenChange(value)
      }}
    >
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Add {roleLabels[role]}</DialogTitle>
          <DialogDescription>
            {role === 'student'
              ? 'Add a student to the registry. They can self-register their account via the mobile app.'
              : `Create a new ${roleLabels[role].toLowerCase()} account.`}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {role === 'student' ? (
            /* ── Student Record Form ── */
            <>
              <div className="space-y-1.5">
                <Label htmlFor="student_id">Student ID *</Label>
                <Input
                  id="student_id"
                  placeholder="21-A-012345"
                  value={form.student_id}
                  onChange={(e) => handleChange('student_id', e.target.value)}
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input
                    id="first_name"
                    placeholder="Juan"
                    value={form.first_name}
                    onChange={(e) => handleChange('first_name', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="middle_name">Middle Name</Label>
                  <Input
                    id="middle_name"
                    placeholder="Santos"
                    value={form.middle_name}
                    onChange={(e) => handleChange('middle_name', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="last_name">Last Name *</Label>
                  <Input
                    id="last_name"
                    placeholder="Dela Cruz"
                    value={form.last_name}
                    onChange={(e) => handleChange('last_name', e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="juan@jrmsu.edu.ph"
                    value={form.email}
                    onChange={(e) => handleChange('email', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="birthdate">Birthdate</Label>
                  <Input
                    id="birthdate"
                    type="date"
                    value={form.birthdate}
                    onChange={(e) => handleChange('birthdate', e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="course">Course</Label>
                  <Input
                    id="course"
                    placeholder="BSCPE"
                    value={form.course}
                    onChange={(e) => handleChange('course', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="year_level">Year Level</Label>
                  <Select
                    value={form.year_level}
                    onValueChange={(v) => handleChange('year_level', v)}
                  >
                    <SelectTrigger id="year_level">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5].map((y) => (
                        <SelectItem key={y} value={String(y)}>
                          {y}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="section">Section</Label>
                  <Input
                    id="section"
                    placeholder="A"
                    value={form.section}
                    onChange={(e) => handleChange('section', e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="contact_number">Contact Number</Label>
                <Input
                  id="contact_number"
                  type="tel"
                  inputMode="numeric"
                  maxLength={11}
                  placeholder="09xxxxxxxxx"
                  value={form.contact_number}
                  onChange={(e) => handleChange('contact_number', e.target.value)}
                />
              </div>
            </>
          ) : (
            /* ── Faculty/Admin Form ── */
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input
                    id="first_name"
                    placeholder="Juan"
                    value={form.first_name}
                    onChange={(e) => handleChange('first_name', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="last_name">Last Name *</Label>
                  <Input
                    id="last_name"
                    placeholder="Dela Cruz"
                    value={form.last_name}
                    onChange={(e) => handleChange('last_name', e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Password *</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="At least 8 characters"
                  value={form.password}
                  onChange={(e) => handleChange('password', e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  type="tel"
                  inputMode="numeric"
                  maxLength={11}
                  placeholder="09xxxxxxxxx"
                  value={form.phone}
                  onChange={(e) => handleChange('phone', e.target.value)}
                />
              </div>
            </>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                `Add ${roleLabels[role]}`
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
