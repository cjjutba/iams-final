/**
 * Strings - Application Text Constants
 *
 * All user-facing text organized by feature/screen.
 * Makes it easy to update copy and prepare for i18n.
 */

export const strings = {
  // App info
  app: {
    name: 'IAMS',
    fullName: 'Intelligent Attendance Monitoring System',
    tagline: 'Smart attendance tracking for JRMSU',
    university: 'Jose Rizal Memorial State University',
    campus: 'Main Campus',
  },

  // Onboarding slides
  onboarding: {
    slides: [
      {
        title: 'Smart Attendance',
        description:
          'Automated attendance tracking using facial recognition technology. No more manual roll calls.',
        icon: 'scan-face',
      },
      {
        title: 'Real-time Monitoring',
        description:
          'Track attendance in real-time. Faculty can monitor classes live, students can check their status instantly.',
        icon: 'activity',
      },
      {
        title: 'Instant Alerts',
        description:
          'Get notified immediately about early departures and attendance issues. Stay informed, stay connected.',
        icon: 'bell',
      },
      {
        title: 'Easy Access',
        description:
          'View schedules, attendance history, and presence scores all in one place. Simple, fast, reliable.',
        icon: 'calendar-check',
      },
    ],
    skip: 'Skip',
    next: 'Next',
    getStarted: 'Get Started',
  },

  // Auth screens
  auth: {
    welcome: 'Welcome to IAMS',
    welcomeStudent: 'Welcome, Student!',
    welcomeFaculty: 'Welcome, Faculty!',
    iAmA: 'I am a...',
    student: 'Student',
    faculty: 'Faculty',
    signIn: 'Sign in',
    signInToContinue: 'Sign in to continue',
    signUp: 'Sign up',
    noAccount: "Don't have an account?",
    hasAccount: 'Already have an account?',
    forgotPassword: 'Forgot Password?',
    resetPassword: 'Reset Password',
    sendResetLink: 'Send Reset Link',
    resetEmailSent: 'Reset link sent! Check your email.',
    resetInstructions: 'Enter your email to receive reset instructions',
    createAccount: 'Create Account',
    termsAgree: 'By continuing, you agree to our Terms of Service and Privacy Policy',
    facultyNotice: 'Faculty accounts are created by administrator',
  },

  // Registration
  register: {
    step1Title: 'Step 1 of 4 - Verify your identity',
    step2Title: 'Step 2 of 4 - Set up your account',
    step3Title: 'Step 3 of 4 - Register your face',
    step4Title: 'Step 4 of 4 - Review your information',
    verifyStudentId: 'Verify Student ID',
    studentIdPlaceholder: '21-A-02177',
    studentFound: 'Student Found',
    isThisYou: 'Is this you?',
    yesContinue: 'Yes, continue',
    faceInstructions: {
      center: 'Look straight ahead',
      left: 'Slowly turn left',
      right: 'Slowly turn right',
      up: 'Slowly look up',
      down: 'Slowly look down',
      noFace: 'Position your face in the oval',
      adjusting: 'Hold steady...',
      complete: 'Face scan complete',
      failed: 'Face scan failed. Please try again.',
    },
    reviewInfo: 'Review your information',
    agreeTerms: 'I agree to the Terms of Service and Privacy Policy',
    facePhotosCaptured: '5 face photos captured',
  },

  // Common UI
  common: {
    next: 'Next',
    back: 'Back',
    submit: 'Submit',
    cancel: 'Cancel',
    save: 'Save',
    delete: 'Delete',
    edit: 'Edit',
    done: 'Done',
    loading: 'Loading...',
    retry: 'Retry',
    skip: 'Skip',
    close: 'Close',
    confirm: 'Confirm',
    yes: 'Yes',
    no: 'No',
    ok: 'OK',
    search: 'Search',
    filter: 'Filter',
    sortBy: 'Sort by',
    refresh: 'Refresh',
    viewDetails: 'View Details',
    noData: 'No data available',
    error: 'Something went wrong',
  },

  // Form labels
  form: {
    email: 'Email',
    password: 'Password',
    confirmPassword: 'Confirm Password',
    currentPassword: 'Current Password',
    newPassword: 'New Password',
    phone: 'Phone Number',
    studentId: 'Student ID',
    firstName: 'First Name',
    lastName: 'Last Name',
    middleName: 'Middle Name',
    course: 'Course',
    year: 'Year',
    section: 'Section',
    department: 'Department',
    remarks: 'Remarks',
    status: 'Status',
  },

  // Validation errors
  errors: {
    network: 'Network error. Please check your connection.',
    generic: 'Something went wrong. Please try again.',
    invalidCredentials: 'Invalid credentials. Please try again.',
    required: 'This field is required',
    invalidEmail: 'Invalid email address',
    invalidPhone: 'Invalid phone number. Format: 09XXXXXXXXX',
    invalidStudentId: 'Invalid Student ID. Format: 21-A-02177',
    passwordMin: 'Password must be at least 8 characters',
    passwordMismatch: 'Passwords do not match',
    serverError: 'Server error. Please try again later.',
    unauthorized: 'Session expired. Please login again.',
  },

  // Attendance
  attendance: {
    present: 'Present',
    late: 'Late',
    absent: 'Absent',
    earlyLeave: 'Early Leave',
    checkInTime: 'Check-in Time',
    checkOutTime: 'Check-out Time',
    presenceScore: 'Presence Score',
    totalScans: 'Total Scans',
    scansPresent: 'Scans Present',
    presenceTimeline: 'Presence Timeline',
    detected: 'Detected',
    notDetected: 'Not Detected',
    confidence: 'Confidence',
    consecutiveMisses: 'Consecutive Misses',
    lastSeen: 'Last Seen',
  },

  // Schedule
  schedule: {
    mySchedule: 'My Schedule',
    todayClasses: "Today's Classes",
    noClassesToday: 'No classes today',
    currentClass: 'Current Class',
    upcomingClass: 'Upcoming Class',
    room: 'Room',
    time: 'Time',
    subject: 'Subject',
    faculty: 'Faculty',
    students: 'Students',
  },

  // Student screens
  student: {
    home: 'Home',
    scheduleTab: 'Schedule',
    history: 'History',
    profile: 'Profile',
    greeting: {
      morning: 'Good morning',
      afternoon: 'Good afternoon',
      evening: 'Good evening',
    },
    editProfile: 'Edit Profile',
    reregisterFace: 'Re-register Face',
    notifications: 'Notifications',
    settings: 'Settings',
    signOut: 'Sign Out',
    changePassword: 'Change Password',
    saveChanges: 'Save Changes',
    faceReregistrationWarning: 'This will replace your existing face registration',
  },

  // Faculty screens
  faculty: {
    home: 'Home',
    scheduleTab: 'Schedule',
    alerts: 'Alerts',
    profile: 'Profile',
    liveAttendance: 'Live Attendance',
    classDetail: 'Class Details',
    studentDetail: 'Student Details',
    manualEntry: 'Manual Entry',
    reports: 'Reports',
    timeRemaining: 'Time Remaining',
    timeElapsed: 'Time Elapsed',
    viewLiveAttendance: 'View Live Attendance',
    generateReport: 'Generate Report',
    exportCsv: 'Export CSV',
    exportPdf: 'Export PDF',
    markAttendance: 'Mark Attendance',
    recentAttendance: 'Recent Attendance',
    attendanceSummary: 'Attendance Summary',
    selectStudent: 'Select Student',
    selectStatus: 'Select Status',
    earlyLeaveAlert: 'Early Leave Alert',
    studentLeftEarly: 'left early',
    noAlertsToday: 'No alerts today',
  },

  // Days of week
  days: {
    sunday: 'Sunday',
    monday: 'Monday',
    tuesday: 'Tuesday',
    wednesday: 'Wednesday',
    thursday: 'Thursday',
    friday: 'Friday',
    saturday: 'Saturday',
    sun: 'Sun',
    mon: 'Mon',
    tue: 'Tue',
    wed: 'Wed',
    thu: 'Thu',
    fri: 'Fri',
    sat: 'Sat',
  },

  // Months
  months: {
    january: 'January',
    february: 'February',
    march: 'March',
    april: 'April',
    may: 'May',
    june: 'June',
    july: 'July',
    august: 'August',
    september: 'September',
    october: 'October',
    november: 'November',
    december: 'December',
  },

  // Time periods
  time: {
    today: 'Today',
    yesterday: 'Yesterday',
    thisWeek: 'This Week',
    thisMonth: 'This Month',
    all: 'All',
    morning: 'Morning',
    afternoon: 'Afternoon',
    evening: 'Evening',
  },

  // Empty states
  empty: {
    noClasses: 'No classes scheduled',
    noAttendance: 'No attendance records found',
    noAlerts: 'No alerts',
    noNotifications: 'No new notifications',
    noStudents: 'No students found',
    noSchedule: 'No schedule available',
  },
} as const;

export type Strings = typeof strings;

