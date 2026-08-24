/**
 * Test JWT retrieval using Neon Auth SDK in Node.js
 * This tests whether authClient.token() works without the JWT plugin
 * Node.js doesn't have CORS restrictions, so this will give a clean test
 */

const NEON_AUTH_URL = 'https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth';

console.log('='.repeat(80));
console.log('NEON AUTH SDK JWT RETRIEVAL TEST (Node.js)');
console.log('='.repeat(80));
console.log(`NEON_AUTH_URL: ${NEON_AUTH_URL}`);
console.log();

// We need to use the Neon Auth SDK
// Since this is Node.js, we'll need to install it first or use a different approach
// Let me try using the undici fetch API which supports Node.js

async function testJwtRetrieval() {
    try {
        console.log('STEP 1: Login to get session token');
        console.log('-'.repeat(80));
        
        const loginResponse = await fetch(`${NEON_AUTH_URL}/sign-in/email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Origin': 'http://localhost:3000',
                'Referer': 'http://localhost:3000'
            },
            body: JSON.stringify({
                email: 'lakshay.kumar@pw.live',
                password: 'Laksh_2005'
            })
        });
        
        console.log(`Login Status: ${loginResponse.status}`);
        
        if (loginResponse.status !== 200) {
            const errorText = await loginResponse.text();
            console.log(`Login failed: ${errorText}`);
            return;
        }
        
        const loginData = await loginResponse.json();
        const sessionToken = loginData.token;
        console.log(`[PASS] Login successful`);
        console.log(`Session token: ${sessionToken.substring(0, 20)}...${sessionToken.substring(sessionToken.length - 10)}`);
        console.log();
        
        // Now try to simulate what authClient.token() would do
        // The SDK likely makes a request to get the JWT, let's try different endpoints
        
        console.log('STEP 2: Try to get JWT via SDK token endpoint simulation');
        console.log('-'.repeat(80));
        
        // Try the /token endpoint (what the SDK likely uses)
        const tokenResponse = await fetch(`${NEON_AUTH_URL}/token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionToken}`,
                'Cookie': `__Secure-neonauth.session_token=${sessionToken}`,
                'Origin': 'http://localhost:3000',
                'Referer': 'http://localhost:3000'
            }
        });
        
        console.log(`Token endpoint status: ${tokenResponse.status}`);
        
        if (tokenResponse.status === 200) {
            const tokenData = await tokenResponse.json();
            console.log(`[PASS] Token endpoint returned data`);
            console.log(`Response: ${JSON.stringify(tokenData, null, 2)}`);
            
            if (tokenData.token || tokenData.jwt) {
                const jwt = tokenData.token || tokenData.jwt;
                console.log(`[PASS] JWT obtained! Length: ${jwt.length}`);
                console.log(`JWT format: ${jwt.substring(0, 50)}...`);
                console.log();
                console.log('CONCLUSION: JWT plugin IS enabled or token endpoint works without it');
            } else {
                console.log(`[INFO] No JWT in response`);
                console.log('CONCLUSION: JWT plugin likely NOT enabled');
            }
        } else if (tokenResponse.status === 404) {
            console.log(`[INFO] Token endpoint returns 404 - JWT plugin not enabled`);
            console.log('CONCLUSION: JWT plugin is NOT enabled');
        } else {
            const errorText = await tokenResponse.text();
            console.log(`[INFO] Token endpoint error: ${errorText}`);
            console.log('CONCLUSION: JWT plugin likely NOT enabled');
        }
        
        console.log();
        
        // Try getSession with proper headers (what browser SDK might do)
        console.log('STEP 3: Try getSession with session cookie (browser simulation)');
        console.log('-'.repeat(80));
        
        const sessionResponse = await fetch(`${NEON_AUTH_URL}/get-session`, {
            method: 'GET',
            headers: {
                'Cookie': `__Secure-neonauth.session_token=${sessionToken}`,
                'Origin': 'http://localhost:3000',
                'Referer': 'http://localhost:3000'
            },
            credentials: 'include'
        });
        
        console.log(`GetSession status: ${sessionResponse.status}`);
        const sessionData = await sessionResponse.text();
        console.log(`GetSession response: ${sessionData.substring(0, 200)}...`);
        
        // Check for JWT in response headers
        const jwtHeader = sessionResponse.headers.get('set-auth-jwt');
        if (jwtHeader) {
            console.log(`[PASS] JWT found in set-auth-jwt header`);
            console.log(`JWT length: ${jwtHeader.length}`);
        } else {
            console.log(`[INFO] No JWT in response headers`);
        }
        
        console.log();
        console.log('='.repeat(80));
        console.log('TEST COMPLETE');
        console.log('='.repeat(80));
        console.log();
        console.log('SUMMARY:');
        console.log('- Session token acquisition: WORKS');
        console.log('- /token endpoint: ' + (tokenResponse.status === 200 ? 'WORKS' : 'FAILS (404)'));
        console.log('- getSession header JWT: ' + (jwtHeader ? 'WORKS' : 'FAILS'));
        console.log();
        console.log('CONCLUSION:');
        if (tokenResponse.status === 200 || jwtHeader) {
            console.log('JWT retrieval is POSSIBLE without explicit plugin configuration');
            console.log('Option B (frontend SDK) may work');
        } else {
            console.log('JWT retrieval is NOT available - JWT plugin is required');
            console.log('Both Option A and Option B require plan upgrade');
        }
        
    } catch (error) {
        console.log(`ERROR: ${error.message}`);
        console.error(error);
    }
}

// Run the test
testJwtRetrieval().catch(console.error);
