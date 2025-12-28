# GraphCeylon User Service

Production-grade user management service built with Express.js, TypeScript, and PostgreSQL.

## Features

- 👤 Complete user CRUD operations
- 🎭 Profile management with avatars
- 👥 Role-based access control (RBAC)
- 📊 User analytics and activity tracking
- 🔍 Advanced search and filtering
- 📧 User preferences management
- 🗄️ PostgreSQL with TypeORM
- 🔄 Database migrations
- ✅ Data validation with Zod

## Tech Stack

- **Runtime**: Node.js 18+
- **Framework**: Express.js 4.x
- **Language**: TypeScript 5.x
- **Database**: PostgreSQL 16.x
- **ORM**: TypeORM 0.3.x
- **Validation**: Zod + class-validator
- **Logging**: Winston
- **Testing**: Jest + Supertest

## Quick Start

### Prerequisites

- Node.js 18+
- PostgreSQL 16+

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Update .env with your configuration
```

### Database Setup

```bash
# Run migrations
npm run migration:run

# Generate new migration
npm run migration:generate -- src/migrations/MigrationName
```

### Development

```bash
# Run in development mode with hot reload
npm run dev

# Run tests
npm test

# Run tests in watch mode
npm run test:watch

# Build for production
npm run build

# Start production server
npm start
```

## API Endpoints

### User Management

- `GET /api/users` - List all users (paginated)
- `GET /api/users/:id` - Get user by ID
- `POST /api/users` - Create new user (admin only)
- `PUT /api/users/:id` - Update user
- `DELETE /api/users/:id` - Delete user (admin only)
- `GET /api/users/search` - Search users
- `GET /api/users/profile/:id` - Get user profile
- `PUT /api/users/profile/:id` - Update user profile

### Analytics

- `GET /api/users/analytics/stats` - Get user statistics
- `GET /api/users/analytics/activity/:id` - Get user activity

### Health Check

- `GET /health` - Service health status

## Architecture

```
user_service/
├── src/
│   ├── config/           # Configuration & database
│   ├── entities/         # TypeORM entities
│   ├── repositories/     # Data access layer
│   ├── services/         # Business logic
│   ├── controllers/      # Request handlers
│   ├── middlewares/      # Express middlewares
│   ├── utils/            # Helper functions
│   ├── types/            # TypeScript types
│   ├── routes/           # API routes
│   ├── app.ts            # Express app setup
│   └── server.ts         # Server entry point
├── migrations/           # Database migrations
├── tests/                # Test suites
└── dist/                 # Compiled JavaScript
```

## Database Schema

### Users Table

- `id` (UUID, PK)
- `email` (VARCHAR, UNIQUE)
- `firstName` (VARCHAR)
- `lastName` (VARCHAR)
- `role` (ENUM: user, admin, moderator)
- `isActive` (BOOLEAN)
- `avatar` (VARCHAR, nullable)
- `bio` (TEXT, nullable)
- `preferences` (JSONB)
- `createdAt` (TIMESTAMP)
- `updatedAt` (TIMESTAMP)
- `lastLoginAt` (TIMESTAMP, nullable)

## Environment Variables

See `.env.example` for all required environment variables.

## Security Features

- JWT authentication verification
- Role-based authorization
- Input validation and sanitization
- SQL injection protection (TypeORM)
- Rate limiting per IP
- Helmet.js for secure headers
- CORS configuration

## Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test -- --coverage

# Run specific test file
npm test -- user.service.test.ts
```

## Docker

```bash
# Build image
docker build -t graphceylon-user-service .

# Run container
docker run -p 8005:8005 --env-file .env graphceylon-user-service
```

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.

## License

MIT
