# Complete Screen List for IAMS

This document defines all screens and navigation for the IAMS React Native mobile app. It aligns with the registration flows and PRD in [docs/main/prd.md](../main/prd.md) and [docs/main/implementation.md](../main/implementation.md).

---

## Shared Screens (All Users)

| Screen | Purpose |
|--------|---------|
| `SplashScreen` | App loading; check auth status and route to onboarding, welcome, or main app |
| `OnboardingScreen` | 4–5 slides introducing the system (what is IAMS, how attendance works, face registration, privacy) |
| `WelcomeScreen` | Role selection (Student or Faculty) |

---

## Auth Screens

| Screen | Purpose |
|--------|---------|
| `StudentLoginScreen` | Student ID + password login |
| `FacultyLoginScreen` | Email + password login (pre-seeded; no self-registration) |
| `ForgotPasswordScreen` | Reset password via email (student or faculty) |

---

## Student Registration Flow

| Screen | Purpose |
|--------|---------|
| `StudentRegisterStep1Screen` | Enter or scan Student ID → validate against university data (CSV/JRMSU) → show name, course, year → user confirms "Is this me?" |
| `StudentRegisterStep2Screen` | Email (pre-filled if from university), phone, password setup |
| `StudentRegisterStep3Screen` | Face registration (3–5 angles capture); upload to backend; backend saves to FAISS |
| `StudentRegisterReviewScreen` | Review all info → agree to terms → submit; backend validates and creates account |

---

## Student Portal

| Screen | Purpose |
|--------|---------|
| `StudentHomeScreen` | Today's classes + attendance status |
| `StudentScheduleScreen` | Weekly class schedule |
| `StudentAttendanceHistoryScreen` | Calendar or list view of past attendance |
| `StudentAttendanceDetailScreen` | Single day detail (presence score, logs) |
| `StudentProfileScreen` | View profile info |
| `StudentEditProfileScreen` | Update email, phone, password |
| `StudentFaceReregisterScreen` | Re-capture face photos (3–5 angles) |
| `StudentNotificationsScreen` | Attendance alerts, early-leave warnings |

---

## Faculty Portal

| Screen | Purpose |
|--------|---------|
| `FacultyHomeScreen` | Today's classes overview |
| `FacultyScheduleScreen` | Weekly teaching schedule |
| `FacultyLiveAttendanceScreen` | Real-time class attendance monitoring |
| `FacultyClassDetailScreen` | Single class attendance summary |
| `FacultyStudentDetailScreen` | Individual student attendance record |
| `FacultyManualEntryScreen` | Manually mark or edit attendance |
| `FacultyEarlyLeaveAlertsScreen` | List of early-leave events |
| `FacultyReportsScreen` | Generate or export attendance reports |
| `FacultyProfileScreen` | View profile info |
| `FacultyEditProfileScreen` | Update email, password |
| `FacultyNotificationsScreen` | Alerts and notifications |

---

## Utility Screens

| Screen | Purpose |
|--------|---------|
| `CameraScreen` | Reusable camera for face capture (used in Step 3 and FaceReregister) |
| `SettingsScreen` | App settings (notifications, theme) |
| `AboutScreen` | App info, version, credits |
| `TermsScreen` | Terms and conditions |
| `PrivacyScreen` | Privacy policy |
| `HelpScreen` | FAQ, contact support |

---

## Screen Flow Diagram

```
App Start
    │
    ▼
SplashScreen
    │
    ├── First time? ──▶ OnboardingScreen ──▶ WelcomeScreen
    │
    └── Returning user?
            │
            ├── Has token + Student ──▶ StudentHomeScreen
            ├── Has token + Faculty ──▶ FacultyHomeScreen
            └── No token ──▶ WelcomeScreen
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            StudentLoginScreen      FacultyLoginScreen
                    │                       │
                    ├── Register?          └── Forgot password? ──▶ ForgotPasswordScreen
                    ▼
            StudentRegisterStep1Screen
                    │
                    ▼
            StudentRegisterStep2Screen
                    │
                    ▼
            StudentRegisterStep3Screen
                    │
                    ▼
            StudentRegisterReviewScreen
                    │
                    ▼
            StudentHomeScreen
```

---

## Navigation Structure

```
Root
├── AuthStack (not logged in)
│   ├── Splash
│   ├── Onboarding
│   ├── Welcome
│   ├── StudentLogin
│   ├── FacultyLogin
│   ├── ForgotPassword
│   └── StudentRegister (nested stack)
│       ├── Step1 (ID verification)
│       ├── Step2 (Account setup)
│       ├── Step3 (Face registration)
│       └── Review
│
├── StudentStack (logged in as student)
│   ├── StudentTabs
│   │   ├── Home
│   │   ├── Schedule
│   │   ├── History
│   │   └── Profile
│   └── Modal / Push screens
│       ├── AttendanceDetail
│       ├── EditProfile
│       ├── FaceReregister
│       ├── Notifications
│       ├── Settings
│       ├── About
│       ├── Terms
│       ├── Privacy
│       └── Help
│
└── FacultyStack (logged in as faculty)
    ├── FacultyTabs
    │   ├── Home
    │   ├── Schedule
    │   ├── Alerts
    │   └── Profile
    └── Modal / Push screens
        ├── LiveAttendance
        ├── ClassDetail
        ├── StudentDetail
        ├── ManualEntry
        ├── Reports
        ├── EditProfile
        ├── Notifications
        ├── Settings
        ├── About
        ├── Terms
        ├── Privacy
        └── Help
```

---

## Screen Count Summary

| Category | Count |
|----------|-------|
| Shared | 3 |
| Auth | 3 |
| Student Registration | 4 |
| Student Portal | 8 |
| Faculty Portal | 11 |
| Utility | 6 |
| **Total** | **35 screens** |

---

## Priority for MVP

### Must Have (Phase 1) — MVP

| Screen | Priority |
|--------|----------|
| SplashScreen | ✅ |
| OnboardingScreen | ✅ |
| WelcomeScreen | ✅ |
| StudentLoginScreen | ✅ |
| FacultyLoginScreen | ✅ |
| StudentRegisterStep1Screen | ✅ |
| StudentRegisterStep2Screen | ✅ |
| StudentRegisterStep3Screen | ✅ |
| StudentRegisterReviewScreen | ✅ |
| StudentHomeScreen | ✅ |
| StudentAttendanceHistoryScreen | ✅ |
| FacultyHomeScreen | ✅ |
| FacultyLiveAttendanceScreen | ✅ |

**MVP = 14 screens.** Focus on these first.

### Should Have (Phase 2)

| Screen | Priority |
|--------|----------|
| ForgotPasswordScreen | ⬜ |
| StudentScheduleScreen | ⬜ |
| FacultyScheduleScreen | ⬜ |
| StudentProfileScreen | ⬜ |
| FacultyProfileScreen | ⬜ |
| FacultyManualEntryScreen | ⬜ |
| StudentNotificationsScreen | ⬜ |
| FacultyNotificationsScreen | ⬜ |

### Nice to Have (Phase 3)

| Screen | Priority |
|--------|----------|
| FacultyReportsScreen | ⬜ |
| StudentFaceReregisterScreen | ⬜ |
| StudentAttendanceDetailScreen | ⬜ |
| FacultyClassDetailScreen | ⬜ |
| FacultyStudentDetailScreen | ⬜ |
| FacultyEarlyLeaveAlertsScreen | ⬜ |
| SettingsScreen | ⬜ |
| AboutScreen | ⬜ |
| TermsScreen | ⬜ |
| PrivacyScreen | ⬜ |
| HelpScreen | ⬜ |

---

## Mapping to Folder Structure (React Native)

Suggested file layout under `mobile/src/screens/`:

| Screen | Suggested path |
|--------|----------------|
| SplashScreen | `screens/SplashScreen.tsx` |
| OnboardingScreen | `screens/onboarding/OnboardingScreen.tsx` |
| WelcomeScreen | `screens/auth/WelcomeScreen.tsx` |
| StudentLoginScreen | `screens/auth/StudentLoginScreen.tsx` |
| FacultyLoginScreen | `screens/auth/FacultyLoginScreen.tsx` |
| ForgotPasswordScreen | `screens/auth/ForgotPasswordScreen.tsx` |
| StudentRegisterStep1Screen | `screens/auth/StudentRegisterStep1Screen.tsx` |
| StudentRegisterStep2Screen | `screens/auth/StudentRegisterStep2Screen.tsx` |
| StudentRegisterStep3Screen | `screens/auth/StudentRegisterStep3Screen.tsx` |
| StudentRegisterReviewScreen | `screens/auth/StudentRegisterReviewScreen.tsx` |
| StudentHomeScreen | `screens/student/StudentHomeScreen.tsx` |
| StudentScheduleScreen | `screens/student/StudentScheduleScreen.tsx` |
| StudentAttendanceHistoryScreen | `screens/student/StudentAttendanceHistoryScreen.tsx` |
| StudentAttendanceDetailScreen | `screens/student/StudentAttendanceDetailScreen.tsx` |
| StudentProfileScreen | `screens/student/StudentProfileScreen.tsx` |
| StudentEditProfileScreen | `screens/student/StudentEditProfileScreen.tsx` |
| StudentFaceReregisterScreen | `screens/student/StudentFaceReregisterScreen.tsx` |
| StudentNotificationsScreen | `screens/student/StudentNotificationsScreen.tsx` |
| FacultyHomeScreen | `screens/faculty/FacultyHomeScreen.tsx` |
| FacultyScheduleScreen | `screens/faculty/FacultyScheduleScreen.tsx` |
| FacultyLiveAttendanceScreen | `screens/faculty/FacultyLiveAttendanceScreen.tsx` |
| FacultyClassDetailScreen | `screens/faculty/FacultyClassDetailScreen.tsx` |
| FacultyStudentDetailScreen | `screens/faculty/FacultyStudentDetailScreen.tsx` |
| FacultyManualEntryScreen | `screens/faculty/FacultyManualEntryScreen.tsx` |
| FacultyEarlyLeaveAlertsScreen | `screens/faculty/FacultyEarlyLeaveAlertsScreen.tsx` |
| FacultyReportsScreen | `screens/faculty/FacultyReportsScreen.tsx` |
| FacultyProfileScreen | `screens/faculty/FacultyProfileScreen.tsx` |
| FacultyEditProfileScreen | `screens/faculty/FacultyEditProfileScreen.tsx` |
| FacultyNotificationsScreen | `screens/faculty/FacultyNotificationsScreen.tsx` |
| CameraScreen | `screens/common/CameraScreen.tsx` |
| SettingsScreen | `screens/common/SettingsScreen.tsx` |
| AboutScreen | `screens/common/AboutScreen.tsx` |
| TermsScreen | `screens/common/TermsScreen.tsx` |
| PrivacyScreen | `screens/common/PrivacyScreen.tsx` |
| HelpScreen | `screens/common/HelpScreen.tsx` |

---

## Notes

- **Face capture:** Use **3–5 angles** (minimum 3, recommended up to 5). See [implementation.md](../main/implementation.md).
- **Faculty:** No self-registration in MVP; faculty accounts are pre-seeded. Message on FacultyLoginScreen: "Faculty accounts are created by the administrator. Contact your department if you need access."
- **Student ID:** Step 1 supports manual entry and optional ID scan/upload; validate against university data (JRMSU/CSV) via backend.
