"""
CI Check: Detect Route/Frontend Divergence

This script compares backend routes with frontend API calls to detect:
1. Frontend calling non-existent backend routes (breaking changes)
2. Backend routes without frontend callers (potential dead code or API-only)

Run in CI to catch breaking changes before deployment.
"""
import sys
import json
import re
from pathlib import Path
from typing import Set, Dict, List

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def extract_backend_routes() -> List[Dict]:
    """Extract all registered FastAPI routes."""
    try:
        from api.main import app
        
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    if method != 'HEAD':
                        routes.append({
                            'method': method,
                            'path': route.path,
                            'name': getattr(route, 'name', None),
                        })
        
        return routes
    except Exception as e:
        print(f"Error extracting backend routes: {e}", file=sys.stderr)
        sys.exit(1)

def extract_frontend_api_calls() -> Set[str]:
    """Extract all API calls from frontend code."""
    frontend_dir = project_root / "frontend" / "src"
    api_calls: Set[str] = set()
    
    # Search through all TypeScript/JavaScript files in src only
    for ts_file in list(frontend_dir.rglob("*.ts")) + list(frontend_dir.rglob("*.tsx")) + list(frontend_dir.rglob("*.js")) + list(frontend_dir.rglob("*.jsx")):
        try:
            content = ts_file.read_text(encoding='utf-8', errors='ignore')
            
            # Look for API calls - more specific pattern
            # Match: `/api/v1/...` in fetch/apiFetch calls
            lines = content.split('\n')
            for line in lines:
                if '/api/v1/' in line and ('fetch(' in line or '"' in line or "'" in line):
                    # Extract URLs from fetch calls
                    fetch_matches = re.findall(r'["\'](/api/v1/[^"\']+)["\']', line)
                    for url in fetch_matches:
                        api_calls.add(url)
        except Exception as e:
            print(f"Error reading {ts_file}: {e}", file=sys.stderr)
    
    return api_calls

def normalize_route(path: str) -> str:
    """Normalize route path for comparison (remove path parameters and query strings)."""
    # Remove query string
    path = path.split('?')[0]
    # Replace path parameters like {id} with placeholders
    return re.sub(r'\{[^}]+\}', '{param}', path)

def check_divergence(backend_routes: List[Dict], frontend_calls: Set[str]) -> Dict:
    """Check for divergences between backend and frontend."""
    # Build backend route set
    backend_routes_set = set()
    for route in backend_routes:
        backend_routes_set.add(f"{route['method']} {route['path']}")
    
    # Build frontend call set (normalize paths)
    frontend_calls_normalized = set()
    for call in frontend_calls:
        # Most frontend calls are GET/POST, but we'll check both
        for method in ['GET', 'POST', 'PATCH', 'DELETE']:
            frontend_calls_normalized.add(f"{method} {call}")
    
    # Check for frontend calls to non-existent routes
    breaking_changes = []
    for call in frontend_calls:
        # Check if any backend route matches this call
        call_normalized = normalize_route(call)
        matched = False
        for route in backend_routes:
            route_normalized = normalize_route(route['path'])
            if call_normalized == route_normalized:
                matched = True
                break
        
        if not matched:
            breaking_changes.append(call)
    
    # Check for backend routes without frontend callers
    uncalled_routes = []
    for route in backend_routes:
        route_path = route['path']
        # Skip documentation and health routes
        if route_path in ['/docs', '/redoc', '/openapi.json', '/health']:
            continue
        # Skip internal routes
        if route_path.startswith('/internal/'):
            continue
        
        # Check if frontend calls this route
        called = False
        for call in frontend_calls:
            call_normalized = normalize_route(call)
            route_normalized = normalize_route(route_path)
            if call_normalized == route_normalized:
                called = True
                break
        
        if not called:
            uncalled_routes.append(f"{route['method']} {route['path']}")
    
    return {
        'breaking_changes': breaking_changes,
        'uncalled_routes': uncalled_routes,
        'total_backend_routes': len(backend_routes),
        'total_frontend_calls': len(frontend_calls),
    }

def main():
    """Main entry point."""
    print("Extracting backend routes...")
    backend_routes = extract_backend_routes()
    
    print("Extracting frontend API calls...")
    frontend_calls = extract_frontend_api_calls()
    
    print("Checking for divergences...")
    divergence = check_divergence(backend_routes, frontend_calls)
    
    # Output results
    print(f"\n=== Route/Frontend Divergence Check ===")
    print(f"Total backend routes: {divergence['total_backend_routes']}")
    print(f"Total frontend API calls: {divergence['total_frontend_calls']}")
    
    if divergence['breaking_changes']:
        print(f"\n[X] BREAKING CHANGES ({len(divergence['breaking_changes'])}):")
        for change in divergence['breaking_changes']:
            print(f"  - Frontend calls: {change} (not found in backend)")
        print("\nThese are breaking changes - frontend will fail!")
        sys.exit(1)
    else:
        print("\n[OK] No breaking changes found")
    
    if divergence['uncalled_routes']:
        print(f"\n[!] UNCALLED BACKEND ROUTES ({len(divergence['uncalled_routes'])}):")
        for route in divergence['uncalled_routes'][:10]:  # Show first 10
            print(f"  - {route}")
        if len(divergence['uncalled_routes']) > 10:
            print(f"  ... and {len(divergence['uncalled_routes']) - 10} more")
        print("\nThese may be API-only routes, feature-gated, or dead code.")
        print("This is a warning, not a failure.")
    else:
        print("\n[OK] All backend routes are called by frontend")
    
    print("\n[OK] Divergence check passed")
    sys.exit(0)

if __name__ == "__main__":
    main()