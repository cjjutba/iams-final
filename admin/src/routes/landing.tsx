import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserPlus, ScanFace, CalendarCheck, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'

const steps = [
  {
    icon: UserPlus,
    title: 'Register',
    description: 'Create your account and register your face',
  },
  {
    icon: ScanFace,
    title: 'Face Scan',
    description: 'Walk into class — recognized automatically',
  },
  {
    icon: CalendarCheck,
    title: 'Attendance',
    description: 'Recorded in real-time, no manual effort',
  },
]

export default function LandingPage() {
  const navigate = useNavigate()

  // If Supabase redirected here with auth tokens in the hash fragment,
  // forward to the email-confirmed page which handles them properly.
  useEffect(() => {
    const hash = window.location.hash
    if (hash && (hash.includes('access_token=') || hash.includes('error='))) {
      navigate(`/auth/email-confirmed${hash}`, { replace: true })
    }
  }, [navigate])

  return (
    <div className="h-screen overflow-hidden bg-background text-foreground">
      <div className="mx-auto flex h-full max-w-sm flex-col items-center justify-between px-6 py-10 sm:py-14">
        {/* Hero + Download */}
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            IAMS
          </h1>
          <p className="mt-2 text-sm text-muted-foreground sm:text-base">
            Intelligent Attendance Monitoring System
          </p>

          <div className="mt-8 w-full max-w-[240px]">
            <Button
              asChild
              className="h-12 w-full gap-2 text-sm font-semibold uppercase tracking-wide"
              size="lg"
            >
              <a href="http://167.71.217.44/iams.apk" download>
                <Download className="h-4 w-4" />
                Download App
              </a>
            </Button>
            <p className="mt-2.5 text-xs text-muted-foreground">
              Available for Android
            </p>
          </div>
        </div>

        {/* Steps + Footer */}
        <div className="w-full shrink-0">
          <div className="mb-5 flex items-center gap-4">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              How it works
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <div className="grid grid-cols-3 gap-4">
            {steps.map((step, i) => (
              <div key={step.title} className="flex flex-col items-center text-center">
                <div className="relative mb-2.5">
                  <span className="absolute -top-1 -right-2 flex h-4 w-4 items-center justify-center rounded-full bg-foreground text-[9px] font-bold text-background">
                    {i + 1}
                  </span>
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border">
                    <step.icon className="h-4.5 w-4.5 text-muted-foreground" strokeWidth={1.5} />
                  </div>
                </div>
                <h3 className="text-xs font-semibold tracking-tight">{step.title}</h3>
                <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
                  {step.description}
                </p>
              </div>
            ))}
          </div>

          <p className="mt-6 text-center text-[10px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
            Jose Rizal Memorial State University
          </p>
        </div>
      </div>
    </div>
  )
}
