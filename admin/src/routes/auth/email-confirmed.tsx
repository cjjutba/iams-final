import { useEffect, useState } from 'react'
import { usePageTitle } from '@/hooks/use-page-title'
import { CheckCircle2, XCircle, KeyRound, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type View = 'loading' | 'verified' | 'reset' | 'reset-success' | 'error'

interface HashParams {
  type: string | null
  accessToken: string | null
  error: string | null
  errorCode: string | null
  errorDescription: string | null
}

function parseHash(): HashParams {
  const hash = window.location.hash.substring(1)
  const params = new URLSearchParams(hash)
  return {
    type: params.get('type'),
    accessToken: params.get('access_token'),
    error: params.get('error'),
    errorCode: params.get('error_code'),
    errorDescription: params.get('error_description'),
  }
}

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string

export default function EmailConfirmedPage() {
  usePageTitle('Email Verification')

  const [view, setView] = useState<View>('loading')
  const [errorTitle, setErrorTitle] = useState('Link Expired')
  const [errorDetail, setErrorDetail] = useState(
    'This verification link has expired or is invalid. Please return to the IAMS app and request a new verification email.'
  )
  const [accessToken, setAccessToken] = useState<string | null>(null)

  // Password reset form state
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    const { type, accessToken: token, error, errorCode } = parseHash()
    setAccessToken(token)

    if (error) {
      if (errorCode === 'otp_expired') {
        setErrorTitle('Link Expired')
        setErrorDetail(
          'This verification link has expired. Please return to the IAMS app and tap "Resend Verification Email" to get a new one.'
        )
      } else if (error === 'access_denied') {
        setErrorTitle('Access Denied')
      }
      setView('error')
    } else if (type === 'recovery' && token) {
      setView('reset')
    } else {
      setView('verified')
    }
  }, [])

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')

    if (password.length < 8) {
      setFormError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setFormError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      const res = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
          apikey: SUPABASE_ANON_KEY,
        },
        body: JSON.stringify({ password }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(
          data.msg || data.error_description || 'Failed to update password'
        )
      }

      setView('reset-success')
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Something went wrong. Please try again.'
      )
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        <h1 className="mb-10 text-3xl font-bold tracking-tight">IAMS</h1>

        {/* Loading */}
        {view === 'loading' && (
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-base text-muted-foreground">Loading...</p>
          </div>
        )}

        {/* Email Verified */}
        {view === 'verified' && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-50">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="text-xl font-semibold">Email Verified</h2>
            <p className="text-base text-muted-foreground leading-relaxed">
              Your email has been confirmed. Return to the IAMS app to sign in.
            </p>
          </div>
        )}

        {/* Password Reset Form */}
        {view === 'reset' && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-50">
              <KeyRound className="h-8 w-8 text-blue-600" />
            </div>
            <h2 className="text-xl font-semibold">Reset Your Password</h2>
            <p className="text-base text-muted-foreground">
              Enter your new password below.
            </p>

            <form onSubmit={handleReset} className="mt-4 w-full space-y-4 text-left">
              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium">
                  New Password
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="At least 8 characters"
                  className="h-12 text-base px-4"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="confirm" className="text-sm font-medium">
                  Confirm Password
                </label>
                <Input
                  id="confirm"
                  type="password"
                  placeholder="Re-enter your password"
                  className="h-12 text-base px-4"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                />
              </div>

              {formError && (
                <p className="text-sm text-destructive">{formError}</p>
              )}

              <Button
                type="submit"
                className="h-12 w-full text-base font-semibold uppercase tracking-wide"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Updating...
                  </>
                ) : (
                  'Update Password'
                )}
              </Button>
            </form>
          </div>
        )}

        {/* Password Reset Success */}
        {view === 'reset-success' && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-50">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="text-xl font-semibold">Password Updated</h2>
            <p className="text-base text-muted-foreground leading-relaxed">
              Your password has been changed successfully. Return to the IAMS app to sign in.
            </p>
          </div>
        )}

        {/* Error */}
        {view === 'error' && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-50">
              <XCircle className="h-8 w-8 text-red-600" />
            </div>
            <h2 className="text-xl font-semibold">{errorTitle}</h2>
            <p className="text-base text-muted-foreground leading-relaxed">
              {errorDetail}
            </p>
          </div>
        )}

        <p className="mt-12 text-xs text-muted-foreground">
          &copy; 2026 IAMS. All rights reserved.
        </p>
      </div>
    </div>
  )
}
