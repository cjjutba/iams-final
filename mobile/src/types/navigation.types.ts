/**
 * Navigation Types
 *
 * Type definitions for React Navigation routes and params.
 * Provides type-safety for navigation throughout the app.
 */

import { NavigatorScreenParams } from '@react-navigation/native';

// Student registration flow data (passed between steps)
export interface RegistrationFlowData {
  step1?: {
    student_id: string;
    first_name: string;
    last_name: string;
    course: string;
    year: string;
    section: string;
    email: string;
  };
  step2?: {
    email: string;
    phone: string;
    password: string;
  };
  step3?: {
    images: string[]; // Base64-encoded face images
  };
}

// Student info returned from Step 1 verification
export interface StudentInfo {
  studentId: string;
  first_name: string;
  last_name: string;
  course: string;
  year: string;
  section: string;
  email?: string;
  phone?: string; // contact_number from student_records
  valid?: boolean;
}

// Account info collected in Step 2
export interface AccountInfo {
  email: string;
  phone: string;
  password: string;
}

// Auth Stack (Onboarding, Login, Registration, Verification)
export type AuthStackParamList = {
  Splash: undefined;
  Onboarding: undefined;
  Welcome: undefined;
  StudentLogin: undefined;
  FacultyLogin: undefined;
  ForgotPassword: undefined;
  EmailVerification: undefined;
  ResetPassword: undefined;
  RegisterStep1: undefined;
  RegisterStep2: {
    studentInfo: StudentInfo;
  };
  RegisterStep3: {
    studentInfo: StudentInfo;
    accountInfo: AccountInfo;
  };
  RegisterReview: {
    studentInfo: StudentInfo;
    accountInfo: AccountInfo;
    faceImages: string[];
  };
};

// Student Tab Navigator
export type StudentTabParamList = {
  StudentHome: undefined;
  StudentSchedule: undefined;
  StudentHistory: undefined;
  StudentProfile: undefined;
};

// Student Stack (includes tabs + modal screens)
export type StudentStackParamList = {
  StudentTabs: NavigatorScreenParams<StudentTabParamList>;
  AttendanceDetail: {
    attendanceId: string;
    scheduleId: string;
    date: string;
  };
  EditProfile: undefined;
  FaceRegister: {
    mode: 'register' | 'reregister';
  };
  Notifications: undefined;
  Settings: undefined;
};

// Faculty Tab Navigator
export type FacultyTabParamList = {
  FacultyHome: undefined;
  FacultySchedule: undefined;
  FacultyAlerts: undefined;
  FacultyProfile: undefined;
};

// Faculty Stack (includes tabs + modal screens)
export type FacultyStackParamList = {
  FacultyTabs: NavigatorScreenParams<FacultyTabParamList>;
  LiveAttendance: {
    scheduleId: string;
    subjectCode: string;
    subjectName: string;
  };
  ClassDetail: {
    scheduleId: string;
    date: string;
  };
  StudentDetail: {
    studentId: string;
    scheduleId: string;
  };
  ManualEntry: {
    scheduleId: string;
  };
  Reports: {
    scheduleId?: string;
  };
  EditProfile: undefined;
  Notifications: undefined;
  Settings: undefined;
};

// Root Stack (Auth or App based on auth state)
export type RootStackParamList = {
  Auth: NavigatorScreenParams<AuthStackParamList>;
  Student: NavigatorScreenParams<StudentStackParamList>;
  Faculty: NavigatorScreenParams<FacultyStackParamList>;
};

// Declare global types for navigation
declare global {
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
