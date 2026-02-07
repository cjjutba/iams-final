# Acceptance Criteria

## Module-Level
- Student can move from app entry to authenticated home flow.
- Registration enforces step validation and blocks invalid progression.
- Dashboard/history/profile screens render with robust UI states.
- Notification screen updates from realtime stream and survives reconnect.

## Function-Level

### FUN-09-01
- First-time users see onboarding.
- Returning users route correctly by session state.

### FUN-09-02
- Login success stores session securely.
- Invalid or expired session is handled gracefully.

### FUN-09-03
- All four registration steps are required and validated.
- Face step requires valid 3-5 images before continue.

### FUN-09-04
- Home/history/detail data reflects backend response accurately.
- Empty/error states are visible and non-blocking.

### FUN-09-05
- Profile edits persist successfully.
- Face re-registration updates status and user feedback.

### FUN-09-06
- Incoming events appear in notifications list.
- Temporary network loss recovers via reconnect.
