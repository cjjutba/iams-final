export interface Room {
  id: string
  name: string
  building: string | null
  capacity: number | null
  camera_endpoint: string | null
  /**
   * mediamtx path the room publishes to (e.g. "eb226"). Derivable from
   * `camera_endpoint` (`rtsp://host:port/{stream_key}`) but the backend
   * also stores it as a first-class field so the live-feed code doesn't
   * have to re-parse the URL on every request.
   */
  stream_key: string | null
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
