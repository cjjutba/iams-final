# Function Specifications

## FUN-09-01 Onboarding and Welcome Flow
Goal:
- Guide first-time users and route them to student or faculty entry paths.

Inputs:
- First-launch flag, saved auth/session state.

Process:
1. Show splash and evaluate startup state.
2. If first launch, show onboarding slides.
3. Navigate to welcome screen for role selection.
4. Route student selection to student login/register path.

Outputs:
- Correct starting route for student user journey.

Validation Rules:
- Onboarding should not block returning authenticated users.
- Navigation transitions must be deterministic and testable.

## FUN-09-02 Student Login and Token Persistence
Goal:
- Authenticate student and persist session securely across app restarts.

Inputs:
- Student credentials and auth API responses.

Process:
1. Submit login request.
2. Validate response and fetch current user profile.
3. Save tokens/session metadata using secure storage.
4. Hydrate auth state on app restart.

Outputs:
- Active authenticated student session.

Validation Rules:
- Invalid credentials show clear errors.
- Expired token path triggers refresh or re-login.

## FUN-09-03 Four-Step Student Registration
Goal:
- Complete student registration with strict validation gates.

Inputs:
- Step payloads: student ID, account details, face images, confirmation.

Process:
1. Step 1: verify student ID with backend.
2. Step 2: collect account details and validate fields.
3. Step 3: capture/upload 3-5 face images.
4. Step 4: review and submit final payload.

Outputs:
- Registered student account with linked face registration.

Validation Rules:
- No step skipping.
- Face registration rejects invalid images and insufficient count.

## FUN-09-04 Attendance Dashboard and History
Goal:
- Show student attendance status, class schedule, and historical records.

Inputs:
- Authenticated user context and attendance/schedule API results.

Process:
1. Fetch dashboard data for current context.
2. Fetch schedule and attendance history.
3. Render lists/details with loading, empty, and error states.

Outputs:
- Student-facing attendance insights across home/history/detail screens.

Validation Rules:
- Date filters and sorting must be stable.
- Unauthorized responses should route to auth recovery.

## FUN-09-05 Profile and Face Re-Registration
Goal:
- Allow student to manage profile fields and renew face registration.

Inputs:
- Profile edits, current user info, face capture uploads.

Process:
1. Load profile from `/auth/me` and related user endpoint.
2. Submit validated profile edits.
3. Check face status and perform re-registration flow when requested.

Outputs:
- Updated profile and refreshed face registration state.

Validation Rules:
- Profile field validation must match backend constraints.
- Re-registration requires authenticated student context.

## FUN-09-06 Student Notifications
Goal:
- Display notification events and keep feed updated in realtime.

Inputs:
- Notification event stream from websocket and optional local cache.

Process:
1. Connect websocket for authenticated user.
2. Receive and render event items by type.
3. Handle disconnect/reconnect with visible state feedback.

Outputs:
- Live student notification feed.

Validation Rules:
- Feed must not crash on unknown/invalid payload.
- Reconnect path must recover without app restart.
