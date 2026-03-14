import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth.store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const loginSchema = z.object({
  identifier: z.string().min(1, 'Email is required'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  usePageTitle('Login')
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginForm) => {
    setError(null)
    try {
      await login(data.identifier, data.password)
      toast.success('Signed in successfully')
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Please try again.'
      setError(message)
      toast.error(message)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-10 text-center">
          <h1 className="text-3xl font-bold tracking-tight">IAMS Admin</h1>
          <p className="mt-2 text-base text-muted-foreground">
            Sign in to your account
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {error && (
            <div className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Input
              id="identifier"
              type="text"
              placeholder="Email"
              autoComplete="email"
              className="h-12 text-base px-4"
              {...register('identifier')}
            />
            {errors.identifier && (
              <p className="text-xs text-destructive">{errors.identifier.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Input
              id="password"
              type="password"
              placeholder="Password"
              autoComplete="current-password"
              className="h-12 text-base px-4"
              {...register('password')}
            />
            {errors.password && (
              <p className="text-xs text-destructive">{errors.password.message}</p>
            )}
          </div>

          <Button
            type="submit"
            className="h-12 w-full text-base font-semibold uppercase tracking-wide"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign in'
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}
