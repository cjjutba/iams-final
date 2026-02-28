/**
 * Face Recognition Types
 *
 * Type definitions for face registration and recognition.
 */

// Face registration response (POST /face/register)
export interface FaceRegisterResponse {
  success: boolean;
  message: string;
  embedding_id: string;
  user_id: string;
}

// Face status response (GET /face/status)
export interface FaceStatusResponse {
  registered: boolean;
  registered_at?: string; // ISO datetime
  embedding_id?: string;
}

// Face recognition response (POST /face/recognize - testing endpoint)
export interface FaceRecognizeResponse {
  success: boolean;
  matched: boolean;
  user_id?: string;
  confidence?: number; // 0-1
  student_name?: string;
}

// Edge API process request (from Raspberry Pi)
export interface EdgeProcessRequest {
  room_id: string;
  timestamp: string; // ISO datetime
  faces: FaceData[];
}

// Face data from edge device
export interface FaceData {
  image: string; // Base64-encoded JPEG
  bbox?: number[]; // Bounding box [x, y, w, h]
}

// Edge API process response
export interface EdgeProcessResponse {
  success: boolean;
  data: {
    processed: number;
    matched: MatchedUser[];
    unmatched: number;
  };
}

// Matched user from face recognition
export interface MatchedUser {
  user_id: string;
  confidence: number;
  student_name?: string;
}

// Face registration data (for multi-step registration flow)
export interface FaceRegistrationData {
  images: string[]; // Array of Base64-encoded images
  angles: string[]; // Array of angle descriptions (e.g., "front", "left", "right")
  user_id?: string;
}
