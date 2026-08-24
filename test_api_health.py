import asyncio
import httpx

async def test_endpoints():
    """Test if API endpoints are working after schema fix."""
    base_url = "http://localhost:5177"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test health endpoint
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Health endpoint: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Health endpoint error: {type(e).__name__}: {e}")
        
        # Test dashboard endpoint (without auth should fail)
        try:
            response = await client.get(f"{base_url}/api/v1/dashboard")
            print(f"Dashboard endpoint: {response.status_code}")
            if response.status_code != 200:
                print(f"Expected auth error: {response.text[:200]}")
        except Exception as e:
            print(f"Dashboard endpoint error: {type(e).__name__}: {e}")

asyncio.run(test_endpoints())