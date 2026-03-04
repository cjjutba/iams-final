/**
 * Schedule Types
 *
 * Type definitions for class schedules, rooms, and subjects.
 */

// Nested faculty info from backend ScheduleResponse
export interface ScheduleFaculty {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

// Nested room info from backend ScheduleResponse
export interface ScheduleRoom {
  id: string;
  name: string;
  building: string;
  capacity?: number;
}

// Schedule (class) definition
export interface Schedule {
  id: string;
  subject_code: string;
  subject_name: string;
  faculty_id: string;
  faculty_name?: string; // Derived from faculty.first_name + faculty.last_name
  room_id: string;
  room_name?: string; // Derived from room.name
  day_of_week: number; // 0=Monday, 6=Sunday
  start_time: string; // HH:MM:SS format
  end_time: string; // HH:MM:SS format
  semester?: string; // e.g., "1st Semester"
  academic_year?: string; // e.g., "2024-2025"
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
  // Nested objects from backend (kept for detailed views)
  faculty?: ScheduleFaculty;
  room?: ScheduleRoom;
}

// Schedule with attendance status (for student home view)
export interface ScheduleWithAttendance extends Schedule {
  today_attendance?: {
    id: string;
    status: string;
    check_in_time?: string;
    presence_score?: number;
  };
}

// Schedule with enrolled students (for faculty views)
export interface ScheduleWithStudents extends Schedule {
  enrolled_students: {
    id: string;
    student_id: string;
    first_name: string;
    last_name: string;
    email: string;
  }[];
}

// Room definition
export interface Room {
  id: string;
  name: string;
  building?: string;
  capacity?: number;
  camera_endpoint?: string; // IP/URL of RPi camera
  is_active: boolean;
  created_at: string;
}

// Enrollment (student-schedule relationship)
export interface Enrollment {
  id: string;
  student_id: string;
  schedule_id: string;
  enrolled_at: string;
  is_active: boolean;
}

// Day of week helper
export enum DayOfWeek {
  MONDAY = 0,
  TUESDAY = 1,
  WEDNESDAY = 2,
  THURSDAY = 3,
  FRIDAY = 4,
  SATURDAY = 5,
  SUNDAY = 6,
}

export const DAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

export const DAY_NAMES_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
