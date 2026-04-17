# Immediate Face Upload During Registration

**Date:** 2026-04-10
**Status:** Approved

## Problem

Face images captured during student registration are saved locally on the phone and only uploaded after the student logs in (`StudentHomeViewModel` triggers `PendingFaceUploadManager`). If the student never logs in on that device, face data never reaches the backend, and the FAISS index stays empty — causing all faces to show as "Unknown" in the live feed.

Additionally, `PendingFaceUploadManager` deletes pending images on failure (lines 80, 86), making retry impossible.

## Solution

Upload face images immediately after account creation using the tokens returned by the registration endpoint, before navigating to login. Add retry on failure.

### New Flow

```
Register Account → Get tokens → Upload faces immediately → Navigate to Login
                                       ↓ (if fails)
                               Show error + Retry button
```

## Changes

### 1. `RegistrationViewModel`

- Add `accountCreated: Boolean` and `faceUploadFailed: Boolean` to `RegistrationUiState`
- In `register()`: on success, save returned tokens to `TokenManager`, set `accountCreated = true` (not `registrationComplete`)
- Add `TokenManager` as a constructor dependency

### 2. `RegisterReviewScreen`

- `LaunchedEffect(accountCreated)`: when true and faces exist, call `uploadFaceImages()`
- Show upload progress UI ("Uploading face data...")
- On upload success → set `registrationComplete = true` → navigate to login
- On upload failure → set `faceUploadFailed = true`, show error + "Retry" button
- Retry button calls `uploadFaceImages()` again
- If no faces captured → set `registrationComplete = true` directly (skip upload)

### 3. `PendingFaceUploadManager`

- Only call `cleanup()` on success
- On failure/exception: keep files for retry, don't call cleanup

### 4. Token cleanup

Tokens saved during registration are naturally overwritten when the student logs in. No explicit clearing needed.

## What stays the same

- Backend `POST /face/register` — no changes
- `StudentHomeViewModel` pending upload check — stays as fallback
- Face capture screens (Step 3) — no changes

## Lessons

- Two-phase registration (save locally → upload later) is fragile — deferred uploads depend on the user logging in on the same device.
- Never delete retry data on failure — `cleanup()` on error paths destroys the only copy of captured face images.
