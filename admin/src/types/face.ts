export interface FaceRegistration {
  id: string
  user_id: string
  embedding_id: string
  registered_at: string
  is_active: boolean
}

export interface FaceStatistics {
  total_registered: number
  total_active: number
  total_inactive: number
}
