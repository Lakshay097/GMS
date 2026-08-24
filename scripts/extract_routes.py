"""
Script to extract all registered FastAPI routes for security audit.
This provides ground truth of all live endpoints, not what's written in files.
"""
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from api.main import app
    
    # Extract all routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            for method in route.methods:
                if method != 'HEAD':  # Skip HEAD methods
                    routes.append({
                        'method': method,
                        'path': route.path,
                        'name': getattr(route, 'name', None),
                        'tags': getattr(route, 'tags', [])
                    })
    
    # Sort by path then method
    routes.sort(key=lambda x: (x['path'], x['method']))
    
    # Output as JSON
    print(json.dumps(routes, indent=2))
    
except Exception as e:
    print(f"Error extracting routes: {e}", file=sys.stderr)
    sys.exit(1)