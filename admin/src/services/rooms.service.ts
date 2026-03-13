import api from './api'
import type { Room, RoomCreate, RoomUpdate } from '@/types'

export const roomsService = {
  list: () =>
    api.get<Room[]>('/rooms').then(r => r.data),
  getById: (id: string) =>
    api.get<Room>(`/rooms/${id}`).then(r => r.data),
  create: (data: RoomCreate) =>
    api.post<Room>('/rooms', data).then(r => r.data),
  update: (id: string, data: RoomUpdate) =>
    api.patch<Room>(`/rooms/${id}`, data).then(r => r.data),
  delete: (id: string) =>
    api.delete(`/rooms/${id}`).then(r => r.data),
  lookup: (name: string) =>
    api.get('/rooms/lookup', { params: { name } }).then(r => r.data),
}
