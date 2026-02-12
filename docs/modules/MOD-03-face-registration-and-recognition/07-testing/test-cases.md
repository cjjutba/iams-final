# Test Cases (MOD-03)

## Unit Tests
| ID | Function | Scenario | Expected |
|---|---|---|---|
| T03-U1 | FUN-03-01 | valid 3-5 image set | accepted |
| T03-U2 | FUN-03-01 | image with no face | rejected |
| T03-U3 | FUN-03-02 | generate embedding | 512-d vector |
| T03-U4 | FUN-03-04 | known match score above threshold | matched=true |
| T03-U5 | FUN-03-04 | unknown face below threshold | matched=false |
| T03-U6 | FUN-03-03 | re-registration sync flow | old mapping handled + new active mapping |
| T03-U7 | FUN-03-02 | image resize to 160x160 | correct model input dimensions |
| T03-U8 | FUN-03-04 | API key validation | valid key accepted, invalid key rejected |
| T03-U9 | FUN-03-03 | face data cleanup on user deletion | face_registrations deleted + FAISS entry removed |

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T03-I1 | POST /face/register | valid images + valid Supabase JWT | `201`, registration metadata |
| T03-I2 | POST /face/register | invalid images + valid Supabase JWT | `400` |
| T03-I3 | POST /face/recognize | registered face + valid API key | `200`, matched=true |
| T03-I4 | POST /face/recognize | unknown face + valid API key | `200`, matched=false |
| T03-I5 | GET /face/status | active registration + valid Supabase JWT | `200`, registered=true |
| T03-I6 | GET /face/status | no active registration + valid Supabase JWT | `200`, registered=false |
| T03-I7 | POST /face/register | no Supabase JWT | `401` |
| T03-I8 | POST /face/register | expired Supabase JWT | `401` |
| T03-I9 | GET /face/status | no Supabase JWT | `401` |
| T03-I10 | POST /face/recognize | no API key | `401` |
| T03-I11 | POST /face/recognize | invalid API key | `401` |
| T03-I12 | POST /face/register | inactive user (is_active=false) | `403` |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T03-E1 | step-3 face registration in student onboarding | registration success with Supabase JWT |
| T03-E2 | student face re-registration flow | old mapping replaced by new mapping |
| T03-E3 | edge recognize request with known face + API key | identity returned with confidence |
| T03-E4 | edge recognize request with unknown face + API key | unmatched result returned |
| T03-E5 | MOD-02 deletes user with face registration | face_registrations and FAISS entry cleaned up |
| T03-E6 | student with unconfirmed email tries face register | `403` returned |
