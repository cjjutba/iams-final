# Registration Draft Schema

## Auth Context
Registration Steps 1-2 are pre-auth (no JWT). After Step 2, the user receives tokens and Steps 3-4 are post-auth.

## Step 1: Identity Verification Draft
| Field | Type | Source |
|---|---|---|
| `student_id` | string | User input |
| `verification_result` | boolean | Backend response from `POST /auth/verify-student-id` (pre-auth) |
| `verified_profile_snapshot` | object | Backend response: `{ first_name, last_name, course, year, section, email }` |

## Step 2: Account Setup Draft
| Field | Type | Source |
|---|---|---|
| `email` | string | Pre-filled from Step 1 snapshot, user-editable |
| `password` | string | User input |
| `confirm_password` | string | User input (client-side validation only) |
| `first_name` | string | Pre-filled from Step 1 snapshot |
| `last_name` | string | Pre-filled from Step 1 snapshot |

**Note**: After `POST /auth/register` succeeds, tokens are returned and stored in SecureStore. User transitions to post-auth.

## Step 3: Face Registration Draft
| Field | Type | Source |
|---|---|---|
| `captured_images[]` | File[] | Camera capture (3-5 images) |
| `validation_results[]` | boolean[] | Client-side face detection check per image |

**Auth**: Post-auth — `POST /face/register` requires JWT from Step 2.

## Step 4: Review Draft
| Field | Type | Source |
|---|---|---|
| `terms_accepted` | boolean | User confirmation |
| `final_payload_ready` | boolean | Computed from Steps 1-3 completion |

## Flow Rules
- Draft data persists only for active registration session (Zustand store).
- Draft is cleared on successful submit or explicit cancel.
- No step skipping — each step must complete before the next enables.
- Step 1 validates against `student_records` table; rejects unknown/duplicate IDs.
- Step 3 requires minimum 3, maximum 5 face images.
