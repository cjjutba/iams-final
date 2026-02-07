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

## Integration Tests
| ID | Endpoint | Scenario | Expected |
|---|---|---|---|
| T03-I1 | POST /face/register | valid images | `201`, registration metadata |
| T03-I2 | POST /face/register | invalid images | `400` |
| T03-I3 | POST /face/recognize | registered face | `200`, matched=true |
| T03-I4 | POST /face/recognize | unknown face | `200`, matched=false |
| T03-I5 | GET /face/status | active registration exists | `200`, registered=true |
| T03-I6 | GET /face/status | no active registration | `200`, registered=false |

## E2E Cases
| ID | Flow | Expected |
|---|---|---|
| T03-E1 | step-3 face registration in student onboarding | registration success |
| T03-E2 | student face re-registration flow | old mapping replaced by new mapping |
| T03-E3 | edge recognize request with known face | identity returned with confidence |
| T03-E4 | edge recognize request with unknown face | unmatched result returned |
