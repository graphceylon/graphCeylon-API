# API Testing with Postman/Insomnia

## Auth Service Collection

### 1. Register User

```http
POST http://localhost:8004/api/auth/register
Content-Type: application/json

{
  "email": "john.doe@example.com",
  "password": "SecurePass123!@#",
  "firstName": "John",
  "lastName": "Doe"
}
```

### 2. Login

```http
POST http://localhost:8004/api/auth/login
Content-Type: application/json

{
  "email": "john.doe@example.com",
  "password": "SecurePass123!@#"
}
```

Response:
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "user": {
      "id": "uuid",
      "email": "john.doe@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "role": "user",
      "isEmailVerified": false
    },
    "tokens": {
      "accessToken": "eyJhbGc...",
      "refreshToken": "eyJhbGc...",
      "expiresIn": "15m"
    }
  }
}
```

### 3. Get Current User

```http
GET http://localhost:8004/api/auth/me
Authorization: Bearer {{accessToken}}
```

### 4. Refresh Token

```http
POST http://localhost:8004/api/auth/refresh
Content-Type: application/json

{
  "refreshToken": "eyJhbGc..."
}
```

### 5. Verify Email

```http
POST http://localhost:8004/api/auth/verify-email
Content-Type: application/json

{
  "token": "verification-token-from-email"
}
```

### 6. Forgot Password

```http
POST http://localhost:8004/api/auth/forgot-password
Content-Type: application/json

{
  "email": "john.doe@example.com"
}
```

### 7. Reset Password

```http
POST http://localhost:8004/api/auth/reset-password
Content-Type: application/json

{
  "token": "reset-token-from-email",
  "newPassword": "NewSecurePass123!@#"
}
```

### 8. Logout

```http
POST http://localhost:8004/api/auth/logout
Authorization: Bearer {{accessToken}}
```

---

## User Service Collection

### 1. Get All Users

```http
GET http://localhost:8005/api/users?page=1&limit=20
Authorization: Bearer {{accessToken}}
```

### 2. Get User by ID

```http
GET http://localhost:8005/api/users/{{userId}}
Authorization: Bearer {{accessToken}}
```

### 3. Create User (Admin Only)

```http
POST http://localhost:8005/api/users
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "email": "jane.smith@example.com",
  "firstName": "Jane",
  "lastName": "Smith",
  "role": "user",
  "bio": "Software Developer"
}
```

### 4. Update User (Admin Only)

```http
PUT http://localhost:8005/api/users/{{userId}}
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "firstName": "Jane",
  "lastName": "Doe",
  "isActive": true,
  "role": "moderator"
}
```

### 5. Delete User (Admin Only)

```http
DELETE http://localhost:8005/api/users/{{userId}}
Authorization: Bearer {{accessToken}}
```

### 6. Get User Profile

```http
GET http://localhost:8005/api/users/profile/{{userId}}
Authorization: Bearer {{accessToken}}
```

### 7. Update User Profile

```http
PUT http://localhost:8005/api/users/profile/{{userId}}
Authorization: Bearer {{accessToken}}
Content-Type: application/json

{
  "firstName": "John",
  "lastName": "Doe",
  "bio": "Full Stack Developer passionate about AI",
  "avatar": "https://example.com/avatar.jpg",
  "preferences": {
    "language": "en",
    "theme": "dark",
    "notifications": {
      "email": true,
      "push": false
    },
    "timezone": "Asia/Colombo"
  }
}
```

### 8. Search Users

```http
GET http://localhost:8005/api/users/search?query=john&role=user&isActive=true&page=1&limit=10
Authorization: Bearer {{accessToken}}
```

### 9. Get Users by Role

```http
GET http://localhost:8005/api/users/role/admin?page=1&limit=10
Authorization: Bearer {{accessToken}}
```

### 10. Get User Statistics (Admin Only)

```http
GET http://localhost:8005/api/users/statistics
Authorization: Bearer {{accessToken}}
```

Response:
```json
{
  "success": true,
  "data": {
    "total": 150,
    "active": 145,
    "inactive": 5,
    "byRole": {
      "admin": 3,
      "moderator": 7,
      "user": 140
    },
    "recent": [...]
  }
}
```

---

## Environment Variables for Postman

```
baseUrl_auth: http://localhost:8004
baseUrl_user: http://localhost:8005
accessToken: <will be set after login>
refreshToken: <will be set after login>
userId: <will be set after user creation>
```

---

## Testing Workflow

1. **Register** a new user
2. **Login** to get tokens
3. **Verify email** (check console for token in dev mode)
4. **Get current user** to verify authentication
5. **Update profile** with preferences
6. **Search users** (if admin/moderator)
7. **Get statistics** (if admin)
8. **Logout** when done

---

## Error Response Format

All errors follow this format:

```json
{
  "success": false,
  "message": "Error message",
  "error": {
    "code": "ERROR_CODE",
    "details": "Additional details (dev mode only)"
  },
  "timestamp": "2025-12-23T10:30:00.000Z",
  "requestId": "uuid"
}
```

Common error codes:
- `VALIDATION_ERROR` - Invalid input data
- `AUTHENTICATION_ERROR` - Invalid or missing token
- `AUTHORIZATION_ERROR` - Insufficient permissions
- `NOT_FOUND` - Resource not found
- `CONFLICT_ERROR` - Duplicate resource
- `TOO_MANY_REQUESTS` - Rate limit exceeded
