export * from './auth'
export * from './user'
export * from './schedule'
export * from './room'
export * from './attendance'
export * from './analytics'
export * from './face'
export * from './notification'

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
