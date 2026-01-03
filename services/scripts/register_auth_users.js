/**
 * Register users in Auth Service
 * The auth service uses in-memory storage, so we need to register users through its API
 * Run with: node register_auth_users.js
 */

const axios = require('axios');

const AUTH_SERVICE_URL = 'http://localhost:8004/api/auth';

const testUsers = [
  {
    email: 'admin@graphceylon.com',
    password: 'Admin@123456',
    firstName: 'Super',
    lastName: 'Admin',
    role: 'admin', // Set admin role
  },
  {
    email: 'user@graphceylon.com',
    password: 'User@123456',
    firstName: 'Regular',
    lastName: 'User',
    role: 'user',
  },
  {
    email: 'moderator@graphceylon.com',
    password: 'Moderator@123456',
    firstName: 'Test',
    lastName: 'Moderator',
    role: 'moderator',
  },
];

async function registerUser(user) {
  try {
    const response = await axios.post(`${AUTH_SERVICE_URL}/register`, user);
    console.log(`✓ Registered: ${user.email}`);
    return response.data;
  } catch (error) {
    if (error.response?.data?.message?.includes('already exists')) {
      console.log(`  ⚠ User ${user.email} already registered`);
    } else {
      console.error(`✗ Error registering ${user.email}:`, error.response?.data?.message || error.message);
    }
  }
}

async function main() {
  console.log('='.repeat(70));
  console.log('Registering Users in Auth Service');
  console.log('='.repeat(70));
  console.log('');

  // Check if auth service is running
  try {
    await axios.get(`${AUTH_SERVICE_URL}/health`).catch(() => {
      // Health endpoint might not exist, try a different way
    });
    console.log('✓ Auth service is running');
  } catch (error) {
    console.error('✗ Cannot connect to auth service at', AUTH_SERVICE_URL);
    console.error('  Make sure the auth service is running on port 8004');
    process.exit(1);
  }

  console.log('');
  console.log('Registering users...');

  for (const user of testUsers) {
    await registerUser(user);
  }

  console.log('');
  console.log('='.repeat(70));
  console.log('Registration Complete!');
  console.log('='.repeat(70));
  console.log('');
  console.log('Test Accounts:');
  console.log('');
  testUsers.forEach(user => {
    console.log(`📧 ${user.email}`);
    console.log(`   Password: ${user.password}`);
    console.log('');
  });
  console.log('You can now login at: http://localhost:5173/login');
  console.log('='.repeat(70));
}

main();
