// Test script to verify Neon Auth configuration
const NEON_AUTH_URL = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth";

console.log("Testing Neon Auth endpoint:", NEON_AUTH_URL);

// Test sign-up endpoint
fetch(`${NEON_AUTH_URL}/sign-up/email`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'test@example.com',
    password: 'testpassword123',
    name: 'Test User'
  })
})
.then(response => {
  console.log('Sign-up endpoint status:', response.status);
  return response.text();
})
.then(data => {
  console.log('Sign-up response:', data);
})
.catch(error => {
  console.error('Sign-up error:', error);
});

// Test sign-in endpoint
fetch(`${NEON_AUTH_URL}/sign-in/email`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'test@example.com',
    password: 'testpassword123'
  })
})
.then(response => {
  console.log('Sign-in endpoint status:', response.status);
  return response.text();
})
.then(data => {
  console.log('Sign-in response:', data);
})
.catch(error => {
  console.error('Sign-in error:', error);
});