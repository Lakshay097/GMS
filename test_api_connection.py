import asyncio
import httpx

async def test_api():
    """Test API connection from frontend perspective."""
    base_url = "http://localhost:5177"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test health endpoint
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Health check: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Health check failed: {e}")
        
        # Test KPIs endpoint (should require auth)
        try:
            response = await client.get(f"{base_url}/api/v1/kpis")
            print(f"KPIs endpoint: {response.status_code}")
            if response.status_code == 401:
                print("✓ Correctly requires authentication")
        except Exception as e:
            print(f"KPIs endpoint failed: {e}")

asyncio.run(test_api())