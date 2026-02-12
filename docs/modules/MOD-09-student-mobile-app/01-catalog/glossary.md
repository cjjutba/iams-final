# Glossary

- **Auth stack**: Unauthenticated navigation path before student session is established (pre-auth screens).
- **Student stack**: Authenticated student navigation path (post-auth screens requiring JWT).
- **Pre-auth endpoint**: API endpoint that does not require JWT (e.g., `/auth/login`, `/auth/register`, `/auth/verify-student-id`).
- **Post-auth endpoint**: API endpoint that requires `Authorization: Bearer <token>` header.
- **Backend-issued JWT**: JSON Web Token issued by the FastAPI backend (not Supabase Auth directly). Used for all mobile API calls.
- **Registration draft**: Temporary local data captured across registration steps (cleared on submit or cancel).
- **Token persistence**: Secure local storage (Expo SecureStore) and restore of auth tokens.
- **Session restore**: Loading persisted credentials to re-authenticate app state on app restart.
- **Re-registration**: Replacing existing face registration with fresh 3-5 captures.
- **State hydration**: Loading cached state into runtime Zustand store on app start.
- **UI state triad**: Loading, empty, and error behavior required for all data-driven screens.
- **Event envelope**: WebSocket message format `{ "type": "...", "data": { ... } }` (distinct from HTTP response envelope).
- **HTTP response envelope**: Backend REST response format `{ "success": true/false, "data": {}, "message": "" }` or `{ "success": false, "error": { "code": "", "message": "" } }`. No `details` array in error responses.
- **Timezone (Asia/Manila)**: All backend timestamps use ISO-8601 with +08:00 offset. Mobile displays should format accordingly.
- **Expo SecureStore**: Secure storage mechanism for sensitive data (tokens). Never use plain AsyncStorage for auth tokens.
- **Design system constraints**: Known type-level restrictions on the monochrome UI component library (see `mvp-scope.md`).
