import { create } from 'zustand'
import type { AuthUser } from '@/types'
import { authService } from '@/services/auth.service'

interface AuthState {
  user: AuthUser | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isLoading: true,
  isAuthenticated: false,

  login: async (email, password) => {
    try {
      const response = await authService.login({ identifier: email, password })
      const { access_token, user } = response
      if (user.role !== 'admin') {
        throw new Error('Access denied. Admin role required.')
      }
      localStorage.setItem('access_token', access_token)
      set({ user, token: access_token, isAuthenticated: true })
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'Access denied. Admin role required.') {
        throw err
      }
      const axiosError = err as { response?: { data?: { error?: { message?: string } } } }
      const message = axiosError.response?.data?.error?.message || 'Login failed. Please try again.'
      throw new Error(message)
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({ user: null, token: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ isLoading: false, isAuthenticated: false })
      return
    }
    try {
      const response = await authService.me()
      const user = response.user || response
      if (user.role !== 'admin') {
        localStorage.removeItem('access_token')
        set({ user: null, token: null, isLoading: false, isAuthenticated: false })
        return
      }
      set({ user, token, isLoading: false, isAuthenticated: true })
    } catch {
      localStorage.removeItem('access_token')
      set({ user: null, token: null, isLoading: false, isAuthenticated: false })
    }
  },
}))
