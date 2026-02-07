# Endpoint Contract: PATCH /users/{id}

## Function Mapping
- `FUN-02-03`

## Purpose
Update allowed user profile fields.

## Path Parameter
- `id` (UUID)

## Request Example
```json
{
  "first_name": "Updated Name"
}
```

## Success Response
```json
{
  "success": true,
  "data": {}
}
```

## Error Cases
- `400`: invalid payload / restricted field update
- `401`: missing/invalid token
- `403`: unauthorized update attempt
- `404`: user not found

## Caller Screens
- `SCR-016` StudentEditProfileScreen
- `SCR-028` FacultyEditProfileScreen
