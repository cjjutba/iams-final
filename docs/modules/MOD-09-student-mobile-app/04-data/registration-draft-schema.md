# Registration Draft Schema

## Step 1: Identity Verification Draft
- `student_id`
- `verification_result`
- `verified_profile_snapshot`

## Step 2: Account Setup Draft
- `email`
- `phone`
- `password`
- `confirm_password`

## Step 3: Face Registration Draft
- `captured_images[]`
- `validation_results[]`

## Step 4: Review Draft
- `terms_accepted`
- `final_payload_ready`

## Flow Rules
- Draft data persists only for active registration session.
- Draft is cleared on successful submit or explicit cancel.
