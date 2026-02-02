# Best Practices

## Code Organization

### File Naming
| Type | Convention | Example |
|------|------------|---------|
| Python modules | snake_case | `user_service.py` |
| Python classes | PascalCase | `UserService` |
| Python functions | snake_case | `get_user_by_id` |
| React Native / TS files | PascalCase or camelCase | `LoginScreen.tsx`, `authService.ts` |
| React components | PascalCase | `LoginScreen` |
| Database tables | snake_case, plural | `attendance_records` |

### Import Order (Python)
```
1. Standard library
2. Third-party packages
3. Local modules
```

### Import Order (TypeScript / React Native)
```
1. React / React Native
2. Third-party packages
3. Local components / utils
4. Types
```

---

## API Design

### Endpoint Naming
| Do | Don't |
|----|-------|
| `/users` | `/getUsers` |
| `/users/{id}` | `/getUserById` |
| `/attendance/today` | `/getTodayAttendance` |

### HTTP Methods
| Action | Method |
|--------|--------|
| Get data | GET |
| Create | POST |
| Update (full) | PUT |
| Update (partial) | PATCH |
| Delete | DELETE |

### Status Codes
| Code | Use Case |
|------|----------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (validation error) |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not found |
| 500 | Server error |

### Pagination
```
GET /attendance?page=1&limit=20

Response:
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "pages": 5
  }
}
```

---

## Database

### Query Practices
| Do | Don't |
|----|-------|
| Use parameterized queries | Concatenate SQL strings |
| Select only needed columns | Use SELECT * |
| Add indexes for frequent queries | Index everything |
| Use transactions for multi-step ops | Multiple separate queries |

### Naming Conventions
| Element | Convention |
|---------|------------|
| Tables | plural, snake_case |
| Columns | singular, snake_case |
| Primary key | `id` |
| Foreign key | `{table}_id` |
| Timestamps | `created_at`, `updated_at` |
| Boolean | `is_` or `has_` prefix |

### Migration Rules
- Never edit existing migrations
- One change per migration
- Always test rollback
- Include both up and down

---

## Error Handling

### Backend
| Layer | Handling |
|-------|----------|
| Router | Catch and return HTTP error |
| Service | Raise custom exceptions |
| Repository | Let database errors bubble up |

### Custom Exceptions
```
AuthenticationError → 401
AuthorizationError → 403
NotFoundError → 404
ValidationError → 400
```

### Logging
| Level | Use Case |
|-------|----------|
| DEBUG | Development details |
| INFO | Normal operations |
| WARNING | Unexpected but handled |
| ERROR | Failures needing attention |

### Log Format
```
[timestamp] [level] [module] message
2024-01-15 10:30:00 INFO auth_service User login: user@email.com
```

---

## Security

### Authentication
- Hash passwords with bcrypt
- Use short-lived JWT (30 min)
- Implement refresh tokens
- Invalidate tokens on logout

### Input Validation
- Validate all inputs with Pydantic
- Sanitize user inputs
- Limit file upload sizes
- Check file types

### Secrets Management
- Never commit secrets to git
- Use environment variables
- Use `.env` files locally
- Rotate secrets periodically

### API Security
- Use HTTPS in production
- Implement rate limiting
- Validate JWT on every request
- Check user permissions

---

## Testing

### Test Types
| Type | Coverage Target |
|------|-----------------|
| Unit tests | 80% of services |
| Integration tests | All API endpoints |
| End-to-end tests | Critical flows |

### Test Naming
```
test_{what}_{condition}_{expected}

Examples:
test_login_valid_credentials_returns_token
test_login_invalid_password_returns_401
test_recognize_face_not_registered_returns_null
```

### Test Structure
```
Arrange → Set up test data
Act → Call the function
Assert → Check the result
```

### What to Test
| Test | Don't Test |
|------|------------|
| Business logic | Framework code |
| Edge cases | Getters/setters |
| Error handling | Third-party libraries |
| Integration points | Database internals |

---

## Git Workflow

### Branch Naming
| Type | Format | Example |
|------|--------|---------|
| Feature | `feature/{description}` | `feature/face-registration` |
| Bug fix | `fix/{description}` | `fix/login-error` |
| Hotfix | `hotfix/{description}` | `hotfix/crash-on-startup` |

### Commit Messages
```
type: short description

Types:
feat: New feature
fix: Bug fix
docs: Documentation
refactor: Code refactoring
test: Adding tests
chore: Maintenance
```

### Pull Request Rules
- Keep PRs small (< 400 lines)
- Write clear description
- Link to related issue
- Request review before merge

---

## Performance

### Backend
- Use async database queries
- Cache frequently accessed data
- Paginate large results
- Use connection pooling

### Face Recognition
- Batch process when possible
- Keep FAISS index in memory
- Warm up models on startup
- Use GPU for inference

### Mobile (React Native)
- Lazy load screens
- Cache API responses (AsyncStorage or store)
- Compress images before upload
- Use pagination for lists
- Store Supabase/backend tokens securely

### Edge Device
- Process frames in separate thread
- Skip frames if falling behind
- Compress before sending
- Queue requests during network issues (see implementation.md)

---

## Documentation

### Code Comments
| Do | Don't |
|----|-------|
| Explain why | Explain what (code is clear) |
| Document complex logic | Comment obvious code |
| Keep comments updated | Leave outdated comments |

### Docstrings (Python)
```
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of what this does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this happens
    """
```

### API Documentation
- Use FastAPI auto-docs
- Add examples to schemas
- Document all error responses
- Keep docs updated with code

---

## Monitoring

### What to Monitor
| Metric | Alert Threshold |
|--------|-----------------|
| API response time | > 2 seconds |
| Error rate | > 5% |
| CPU usage | > 90% |
| Memory usage | > 85% |
| Database connections | > 80% pool |

### Logging Best Practices
- Log all API requests
- Log authentication events
- Log errors with stack trace
- Don't log sensitive data

---

## Configuration

### Environment-Based Config
```
Development: .env.development
Testing: .env.test
Production: .env.production
```

### Config Priority
```
1. Environment variables
2. .env file
3. Default values
```

### Secrets Checklist
- [ ] Supabase URL and anon key (use env; anon key is public but rate-limited)
- [ ] Database password / Supabase service role (backend only)
- [ ] JWT secret key (if custom auth)
- [ ] API keys
- [ ] Never in version control
