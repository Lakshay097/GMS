import asyncio
from shared.auth import decode_access_token

# Test with a sample token (you'll need to provide an actual token)
async def test_token_decode():
    # You'll need to get an actual token from the frontend
    # For now, let's test the function exists
    test_token = "test.token.here"
    result = decode_access_token(test_token)
    print(f"Token decode result: {result}")

if __name__ == "__main__":
    asyncio.run(test_token_decode())