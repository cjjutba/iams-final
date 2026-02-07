# Auth Screen Flows

## Student Registration Flow (Auth Portion)
1. `SCR-007` StudentRegisterStep1Screen
- user enters student ID
- app calls `POST /auth/verify-student-id`
- app shows identity preview and confirmation

2. `SCR-008` StudentRegisterStep2Screen
- user enters/updates email, phone, password
- local validation occurs

3. `SCR-010` StudentRegisterReviewScreen
- app submits registration to `POST /auth/register`
- on success, continue to login/session flow

## Student Login Flow
1. `SCR-004` StudentLoginScreen
2. call `POST /auth/login`
3. persist token(s)
4. call `GET /auth/me` to resolve profile context
5. route to student area

## Faculty Login Flow
1. `SCR-005` FacultyLoginScreen
2. call `POST /auth/login`
3. enforce pre-seeded faculty rule
4. call `GET /auth/me`
5. route to faculty area

## Password Recovery Flow
1. `SCR-006` ForgotPasswordScreen
2. submit reset request (implementation details depend on selected auth provider)
3. show success/failure state
