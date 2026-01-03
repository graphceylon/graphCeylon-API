# Auth & User Services Integration Guide

## 🎉 Services Created Successfully!

Two production-grade microservices have been added to your GraphCeylon API:

### 1. **Auth Service** (Port 8004)
- JWT-based authentication with refresh tokens
- Email verification workflow
- Password reset functionality
- Rate limiting & brute-force protection
- Redis for token management
- Comprehensive logging

### 2. **User Service** (Port 8005)
- Complete user CRUD operations
- PostgreSQL database with TypeORM
- Role-based access control (RBAC)
- Profile management
- User search & filtering
- Analytics and statistics

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Auth Service
cd services/auth_service
npm install

# User Service
cd services/user_service
npm install
```

### 2. Setup Environment Variables

```bash
# Auth Service
cd services/auth_service
cp .env.example .env
# Edit .env with your configuration

# User Service
cd services/user_service
cp .env.example .env
# Edit .env with your configuration
```

### 3. Start Infrastructure

```bash
# From project root
cd infra
docker-compose up -d postgres redis

# Wait for databases to be ready
docker-compose ps
```

### 4. Run Services

**Development Mode:**
```bash
# Auth Service
cd services/auth_service
npm run dev

# User Service (in another terminal)
cd services/user_service
npm run dev
```

**Production Mode:**
```bash
# Build and start with Docker Compose
cd infra
docker-compose up -d auth_service user_service
```

---

## 📦 Full Stack with Docker Compose

Start all services together:

```bash
cd infra
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f auth_service user_service
```

---

## 🔑 API Endpoints

### Auth Service (http://localhost:8004)

```
POST   /api/auth/register          - Register new user
POST   /api/auth/login             - Login user
POST   /api/auth/logout            - Logout user
POST   /api/auth/refresh           - Refresh access token
POST   /api/auth/verify-email      - Verify email
POST   /api/auth/forgot-password   - Request password reset
POST   /api/auth/reset-password    - Reset password
GET    /api/auth/me                - Get current user
GET    /health                     - Health check
```

### User Service (http://localhost:8005)

```
GET    /api/users                  - List users (Admin/Moderator)
GET    /api/users/:id              - Get user by ID
POST   /api/users                  - Create user (Admin)
PUT    /api/users/:id              - Update user (Admin)
DELETE /api/users/:id              - Delete user (Admin)
GET    /api/users/search           - Search users
GET    /api/users/profile/:id      - Get user profile
PUT    /api/users/profile/:id      - Update profile
GET    /api/users/statistics       - User statistics (Admin)
GET    /health                     - Health check
```

---

## 🧪 Testing the Services

### 1. Register a User

```bash
curl -X POST http://localhost:8004/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "firstName": "John",
    "lastName": "Doe"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8004/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }'
```

Response includes `accessToken` and `refreshToken`.

### 3. Get Current User

```bash
curl http://localhost:8004/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Create User (Admin)

```bash
curl -X POST http://localhost:8005/api/users \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "firstName": "Jane",
    "lastName": "Smith",
    "role": "user"
  }'
```

### 5. Get All Users

```bash
curl http://localhost:8005/api/users?page=1&limit=10 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 🗄️ Database Setup

### PostgreSQL (User Service)

The database will be created automatically when you start the containers. For manual setup:

```bash
# Connect to PostgreSQL
docker exec -it graphceylon-postgres psql -U postgres

# Create database
CREATE DATABASE graphceylon_users;

# Exit
\q
```

### Redis (Auth Service)

Redis is used for:
- Refresh token storage
- Email verification tokens
- Password reset tokens
- Login attempt tracking

No manual setup required - starts automatically.

---

## 🔒 Security Configuration

### JWT Secrets (IMPORTANT!)

Change these in production:

```env
# Auth Service .env
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_REFRESH_SECRET=your-super-secret-refresh-key-change-in-production
```

### CORS Configuration

Update allowed origins:

```env
CORS_ORIGIN=https://your-frontend-domain.com
```

### Rate Limiting

Adjust as needed:

```env
RATE_LIMIT_WINDOW_MS=900000    # 15 minutes
RATE_LIMIT_MAX_REQUESTS=100    # Max requests per window
```

---

## 📊 Service Architecture

```
┌─────────────────┐
│   Frontend      │
└────────┬────────┘
         │
    ┌────▼────────┐
    │ Orchestrator│ (Port 8002)
    └────┬────────┘
         │
    ┌────┴──────────────────────────────┐
    │                                    │
┌───▼────────┐  ┌──────────────┐  ┌────▼──────┐
│Auth Service│  │User Service  │  │KG Service │
│(Port 8004) │  │(Port 8005)   │  │(Port 8000)│
└────┬───────┘  └──────┬───────┘  └───────────┘
     │                 │
┌────▼────┐      ┌─────▼────────┐
│  Redis  │      │  PostgreSQL  │
└─────────┘      └──────────────┘
```

---

## 🔗 Integration with Existing Services

### Update Orchestrator

Add auth/user service URLs to orchestrator configuration:

```python
# services/orchestrator/src/config.py
AUTH_SERVICE_URL = "http://localhost:8004"
USER_SERVICE_URL = "http://localhost:8005"
```

### Protected Routes

To protect existing Python services:

```python
import requests
from fastapi import HTTPException, Header

def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    
    token = authorization.replace("Bearer ", "")
    
    # Verify with auth service
    response = requests.get(
        "http://localhost:8004/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return response.json()["data"]
```

---

## 📝 Environment Variables Summary

### Auth Service

| Variable | Description | Default |
|----------|-------------|---------|
| PORT | Server port | 8004 |
| JWT_SECRET | JWT signing secret | (required) |
| REDIS_HOST | Redis host | localhost |
| SMTP_HOST | Email SMTP host | smtp.gmail.com |
| FRONTEND_URL | Frontend URL for emails | http://localhost:3000 |

### User Service

| Variable | Description | Default |
|----------|-------------|---------|
| PORT | Server port | 8005 |
| DB_HOST | PostgreSQL host | localhost |
| DB_DATABASE | Database name | graphceylon_users |
| JWT_SECRET | JWT secret (same as auth) | (required) |

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Windows
netstat -ano | findstr :8004
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8004 | xargs kill -9
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

### PostgreSQL Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres
```

### TypeScript Build Errors

```bash
# Clean build
rm -rf dist node_modules
npm install
npm run build
```

---

## 📈 Monitoring & Logs

### View Logs

```bash
# Docker logs
docker-compose logs -f auth_service
docker-compose logs -f user_service

# Local development
# Logs are in services/auth_service/logs/
# Logs are in services/user_service/logs/
```

### Health Checks

```bash
# Auth Service
curl http://localhost:8004/health

# User Service
curl http://localhost:8005/health
```

---

## 🧪 Running Tests

```bash
# Auth Service
cd services/auth_service
npm test
npm run test:watch

# User Service
cd services/user_service
npm test
npm run test:watch
```

---

## 🚢 Production Deployment

### Environment Setup

1. Update all secrets in `.env`
2. Set `NODE_ENV=production`
3. Configure proper SMTP for emails
4. Set up SSL/TLS certificates
5. Configure production database

### Docker Compose Production

```bash
# Build production images
docker-compose build auth_service user_service

# Start services
docker-compose up -d auth_service user_service

# Check status
docker-compose ps
```

---

## 📚 Additional Resources

- [Auth Service README](../services/auth_service/README.md)
- [User Service README](../services/user_service/README.md)
- [TypeORM Documentation](https://typeorm.io)
- [Express.js Documentation](https://expressjs.com)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)

---

## 🎯 Next Steps

1. ✅ Install dependencies for both services
2. ✅ Configure environment variables
3. ✅ Start PostgreSQL and Redis
4. ✅ Run database migrations
5. ✅ Start services and test endpoints
6. ✅ Integrate with orchestrator
7. ✅ Set up production deployment

---

## 💡 Tips

- Use **Postman** or **Insomnia** for API testing
- Keep JWT secrets secure and rotate them regularly
- Monitor Redis memory usage
- Set up database backups for PostgreSQL
- Use proper SMTP service (SendGrid, AWS SES) in production
- Enable HTTPS in production
- Set up proper logging aggregation (ELK, CloudWatch)

---

**Need Help?** Check the individual service README files or review the code comments for detailed information.

Happy coding! 🚀
