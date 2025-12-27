# GraphCeylon Auth Service

Production-grade authentication service built with Express.js and TypeScript.

## Features

- 🔐 JWT-based authentication (Access + Refresh tokens)
- 🔑 OAuth2.0 ready (Google, Facebook integration)
- 🛡️ Rate limiting and brute-force protection
- 🔒 Secure password hashing with bcrypt
- ✉️ Email verification workflow
- 🔄 Password reset functionality
- 📝 Comprehensive audit logging
- 🚀 Production-ready architecture

## Tech Stack

- **Runtime**: Node.js 18+
- **Framework**: Express.js 4.x
- **Language**: TypeScript 5.x
- **Authentication**: JWT (jsonwebtoken)
- **Password Hashing**: bcrypt
- **Validation**: Zod
- **Caching**: Redis
- **Logging**: Winston
- **Testing**: Jest + Supertest

## Quick Start

### Prerequisites

- Node.js 18+
- Redis (for token management)

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Update .env with your configuration
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

### Authentication

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/verify-email` - Verify email address
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset password
- `GET /api/auth/me` - Get current user info

### Health Check

- `GET /health` - Service health status

## Architecture

```
auth_service/
├── src/
│   ├── config/           # Configuration management
│   ├── controllers/      # Request handlers
│   ├── services/         # Business logic
│   ├── middlewares/      # Express middlewares
│   ├── utils/            # Helper functions
│   ├── types/            # TypeScript types
│   ├── routes/           # API routes
│   ├── app.ts            # Express app setup
│   └── server.ts         # Server entry point
├── tests/                # Test suites
├── logs/                 # Application logs
└── dist/                 # Compiled JavaScript
```

## Environment Variables

See `.env.example` for all required environment variables.

## Security Features

- Helmet.js for secure HTTP headers
- Rate limiting per IP
- Brute-force protection
- JWT token rotation
- Password complexity requirements
- XSS protection
- CORS configuration
- Input sanitization

## Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test -- --coverage

# Run specific test file
npm test -- auth.service.test.ts
```

## Logging

Logs are stored in the `logs/` directory:
- `error.log` - Error level logs
- `combined.log` - All logs
- Daily rotation with compression

## Docker

```bash
# Build image
docker build -t graphceylon-auth-service .

# Run container
docker run -p 8004:8004 --env-file .env graphceylon-auth-service
```

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.

## License

MIT
