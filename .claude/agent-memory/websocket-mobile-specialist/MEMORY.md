# WebSocket Mobile Specialist - Memory

## Project Architecture
- Backend: FastAPI at `backend/app/`
- Mobile: React Native (Expo) at `mobile/src/`
- WebSocket endpoint: `ws://{host}/api/v1/ws/{user_id}` (no auth in MVP)
- Backend sends JSON: `{ "event": "...", "data": {...} }` -- note field is `event`, NOT `type`
- Auth state managed by Zustand store (`useAuthStore`) wrapped by `useAuth` hook
- Navigation: RootNavigator conditionally renders Auth/Student/Faculty based on auth state

## Key Bugs Fixed (2026-02-07)
- **websocketService.ts**: Was parsing `message.type` but backend sends `message.event`
- **websocketService.ts**: Fixed interval reconnect -> exponential backoff (1s base, 30s max)
- **websocketService.ts**: Added heartbeat ping/pong, app state listener, connection state machine
- **websocketService.ts**: `disconnect()` was clearing all handlers; now `disconnect()` preserves handlers, `destroy()` clears them
- **useWebSocket.ts**: Callbacks were in dependency array causing reconnect loops; fixed with refs
- **useWebSocket.ts**: `isConnected` was not reactive; now uses `onStateChange` listener
- **StudentLoginScreen**: Imported non-existent `StudentLoginData` type (should be `StudentLoginFormData`)
- **StudentLoginScreen**: Login passed `{ ...data, role: 'student' }` but LoginRequest needs `{ email, password }`; student_id mapped to email field
- **navigation.types.ts**: RegisterStep2/3/Review params used `registrationData: RegistrationFlowData` but screens expected `studentInfo`/`accountInfo`/`faceImages`; fixed types to match screen usage
- **RegisterReviewScreen**: Missing face image upload after account creation; added `faceService.registerFace()` call

## Type Patterns
- `LoginRequest` uses `email` field for both email and student ID
- `WebSocketMessage<T>` has `event: WebSocketEventType | string` and `data: T`
- Navigation params: Step1->Step2 passes `StudentInfo`, Step2->Step3 adds `AccountInfo`, Step3->Review adds `faceImages: string[]`

## React Native WebSocket Gotchas
- RN WebSocket events use `WebSocketMessageEvent` and `WebSocketCloseEvent` types (not standard DOM types)
- AppState listener needed for background/foreground handling
- Set `socket.onclose = null` before closing to prevent recursive reconnect triggers
- `send()` accepts string or object (stringify internally); avoid double-serialization
