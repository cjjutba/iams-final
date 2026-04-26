export * from './auth'
export * from './user'
export * from './schedule'
export * from './room'
export * from './attendance'
export * from './analytics'
export * from './face'
export * from './face-registration-detail'
export * from './notification'
export * from './recognition'
export * from './activity'

export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}
