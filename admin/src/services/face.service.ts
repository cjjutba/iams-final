import api from './api'
import type { FaceStatistics } from '@/types'

export const faceService = {
  statistics: () =>
    api.get<{ success: boolean; data: FaceStatistics }>('/face/statistics').then(r => r.data),
  deregister: (userId: string) =>
    api.delete(`/face/${userId}`).then(r => r.data),
}
