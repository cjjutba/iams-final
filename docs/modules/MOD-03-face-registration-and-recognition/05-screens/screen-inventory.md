# Screen Inventory (MOD-03)

## Included Screens
| Screen ID | Screen Name | Role | Face Module Usage |
|---|---|---|---|
| SCR-009 | StudentRegisterStep3Screen | Student | capture and submit registration images (Supabase JWT) |
| SCR-017 | StudentFaceReregisterScreen | Student | replace existing registration (Supabase JWT) |
| SCR-030 | CameraScreen | Student | shared capture utility for face images |

## Screen-to-Function Mapping
- `SCR-009` -> `FUN-03-01`, `FUN-03-02`, `FUN-03-03`, `FUN-03-05`
- `SCR-017` -> `FUN-03-01`, `FUN-03-02`, `FUN-03-03`, `FUN-03-05`
- `SCR-030` -> capture support for registration flows

## Auth Note
All screens require the user to be authenticated with a valid Supabase JWT (from MOD-01 registration/login flow) before submitting to face endpoints.
