/**
 * Set Admin Role Script
 * After registering users, this script updates the admin user role
 * Run with: node set_admin_role.js
 */

const axios = require('axios');

const AUTH_SERVICE_URL = 'http://localhost:8004/api/auth';

async function setAdminRole() {
  console.log('='.repeat(70));
  console.log('Setting Admin Role');
  console.log('='.repeat(70));
  console.log('');

  try {
    // Login as admin to get token
    console.log('1. Logging in as admin...');
    const loginResponse = await axios.post(`${AUTH_SERVICE_URL}/login`, {
      email: 'admin@graphceylon.com',
      password: 'Admin@123456',
    });

    if (!loginResponse.data.success) {
      console.error('✗ Login failed. Please register first:');
      console.error('  node register_auth_users.js');
      process.exit(1);
    }

    const token = loginResponse.data.data.tokens.accessToken;
    console.log('✓ Login successful');
    console.log('');

    // Get current user data
    console.log('2. Getting current user data...');
    const meResponse = await axios.get(`${AUTH_SERVICE_URL}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    const user = meResponse.data.data;
    console.log(`✓ Current role: ${user.role}`);
    console.log('');

    if (user.role === 'admin') {
      console.log('✅ User is already an admin!');
      console.log('');
      console.log('You can now login at: http://localhost:5173/login');
      console.log('Email: admin@graphceylon.com');
      console.log('Password: Admin@123456');
      return;
    }

    console.log('');
    console.log('⚠️  MANUAL INTERVENTION REQUIRED');
    console.log('='.repeat(70));
    console.log('');
    console.log('The auth service uses in-memory storage and does not support');
    console.log('role updates through the API.');
    console.log('');
    console.log('OPTIONS:');
    console.log('');
    console.log('Option 1: Modify auth service code (RECOMMENDED)');
    console.log('─────────────────────────────────────────────────');
    console.log('Edit: services/auth_service/src/services/auth.service.ts');
    console.log('Line 53: Change from:');
    console.log('  role: UserRole.USER,');
    console.log('To:');
    console.log('  role: data.role || UserRole.USER,');
    console.log('');
    console.log('Then rebuild and restart:');
    console.log('  cd services/auth_service');
    console.log('  npm run build');
    console.log('  npm start');
    console.log('');
    console.log('Option 2: Use a quick hack');
    console.log('─────────────────────────────────────────────────');
    console.log('See: services/scripts/MANUAL_ADMIN_SETUP.md');
    console.log('');

  } catch (error) {
    console.error('✗ Error:', error.response?.data?.message || error.message);
    process.exit(1);
  }
}

setAdminRole();
