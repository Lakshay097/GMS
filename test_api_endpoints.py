import asyncio
import httpx

async def test_endpoints():
    """Test if API endpoints are working after schema fix."""
    base_url = "http://localhost:5177/api/v1"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test dashboard endpoint
        try:
            response = await client.get(f"{base_url}/dashboard")
            print(f"Dashboard endpoint: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text[:200]}")
        except Exception as e:
            print(f"Dashboard endpoint error: {type(e).__name__}: {e}")
        
        # Test KPIs endpoint
        try:
            response = await client.get(f"{base_url}/kpis")
            print(f"KPIs endpoint: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text[:200]}")
        except Exception as e:
            print(f"KPIs endpoint error: {type(e).__name__}: {e}")
        
        # Test observations endpoint
        try:
            response = await client.get(f"{base_url}/observations?date=2026-08-21")
            print(f"Observations endpoint: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text[:200]}")
        except Exception as e:
            print(f"Observations endpoint error: {type(e).__name__}: {e}")

asyncio.run(test_endpoints())