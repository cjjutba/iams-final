export interface Room {
  id: string
  name: string
  building: string | null
  capacity: number | null
  camera_endpoint: string | null
  is_active: boolean
}

export interface RoomCreate {
  name: string
  building?: string
  capacity?: number
  camera_endpoint?: string
}

export interface RoomUpdate {
  name?: string
  building?: string
  capacity?: number
  camera_endpoint?: string
  is_active?: boolean
}
