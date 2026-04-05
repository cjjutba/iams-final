import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MoreHorizontal, Eye, Loader2, Pencil, UserX, UserCheck, ScanFace } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  useDeactivateUser,
  useReactivateUser,
  useDeregisterFace,
} from '@/hooks/use-queries'
import type { UserResponse } from '@/types'
import { EditUserDialog } from './edit-user-dialog'

export function UserActionsCell({ user }: { user: UserResponse }) {
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [reactivateOpen, setReactivateOpen] = useState(false)
  const [deregisterOpen, setDeregisterOpen] = useState(false)

  const deactivateMutation = useDeactivateUser()
  const reactivateMutation = useReactivateUser()
  const deregisterMutation = useDeregisterFace()
  const loading = deactivateMutation.isPending || reactivateMutation.isPending || deregisterMutation.isPending

  const handleDeactivate = async () => {
    try {
      await deactivateMutation.mutateAsync(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been deactivated.`)
    } catch {
      toast.error('Failed to deactivate user.')
    } finally {
      setDeactivateOpen(false)
    }
  }

  const handleReactivate = async () => {
    try {
      await reactivateMutation.mutateAsync(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been reactivated.`)
    } catch {
      toast.error('Failed to reactivate user.')
    } finally {
      setReactivateOpen(false)
    }
  }

  const handleDeregister = async () => {
    try {
      await deregisterMutation.mutateAsync(user.id)
      toast.success(`Face data for ${user.first_name} ${user.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    } finally {
      setDeregisterOpen(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => navigate(`/users/${user.id}`, { state: { role: user.role } })}>
            <Eye className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setEditOpen(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {user.is_active ? (
            <DropdownMenuItem onClick={() => setDeactivateOpen(true)}>
              <UserX className="mr-2 h-4 w-4" />
              Deactivate
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem onClick={() => setReactivateOpen(true)}>
              <UserCheck className="mr-2 h-4 w-4" />
              Reactivate
            </DropdownMenuItem>
          )}
          {user.role === 'student' && (
            <DropdownMenuItem onClick={() => setDeregisterOpen(true)}>
              <ScanFace className="mr-2 h-4 w-4" />
              Deregister Face
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={deactivateOpen} onOpenChange={setDeactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate {user.first_name} {user.last_name}?
              They will no longer be able to access the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDeactivate()
              }}
              disabled={loading}
            >
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deactivating...</>) : 'Deactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={reactivateOpen} onOpenChange={setReactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reactivate User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to reactivate {user.first_name} {user.last_name}?
              They will regain access to the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleReactivate()
              }}
              disabled={loading}
            >
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Reactivating...</>) : 'Reactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deregisterOpen} onOpenChange={setDeregisterOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deregister Face</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove face registration data for{' '}
              {user.first_name} {user.last_name}? They will need to re-register
              their face to use the attendance system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDeregister()
              }}
              disabled={loading}
            >
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Removing...</>) : 'Deregister'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <EditUserDialog user={user} open={editOpen} onOpenChange={setEditOpen} />
    </>
  )
}
