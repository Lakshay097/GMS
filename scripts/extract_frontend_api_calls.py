"""
Script to extract all API calls from the frontend codebase.
This provides a comprehensive list of what the frontend actually calls.
"""
import re
import json
import sys
from pathlib import Path
from typing import Set, Dict, List

# Search for API patterns in frontend code
frontend_dir = Path(__file__).parent.parent / "frontend"

api_calls: Set[str] = set()
api_call_details: List[Dict] = []

# Search through all TypeScript/JavaScript files
for ts_file in list(frontend_dir.rglob("*.ts")) + list(frontend_dir.rglob("*.tsx")) + list(frontend_dir.rglob("*.js")) + list(frontend_dir.rglob("*.jsx")):
    try:
        content = ts_file.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Look for common API call patterns
            if 'fetch(' in line or 'apiFetch(' in line or 'fetchWithAuth(' in line:
                # Extract URLs from fetch calls
                fetch_matches = re.findall(r'["\']([^"\']+api/[^"\']+)["\']', line)
                for url in fetch_matches:
                    api_calls.add(url)
                    api_call_details.append({
                        'file': str(ts_file.relative_to(frontend_dir)),
                        'line': line_num,
                        'url': url,
                        'context': line.strip()
                    })
    except Exception as e:
        print(f"Error reading {ts_file}: {e}", file=sys.stderr)

# Sort and output
sorted_calls = sorted(api_calls)
print(json.dumps({
    'total_unique_calls': len(sorted_calls),
    'api_calls': sorted_calls,
    'call_details': api_call_details
}, indent=2))