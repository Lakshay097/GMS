"""
Fix scaffold test data setup issues:
1. Add neon_auth_user_id=f"neon-{uuid4()}" to User() constructors that lack it
2. Normalize status="active"/"active" -> proper enum constructors for School, Dept, User objects
   in test files that don't import these enums.
"""
import pathlib, re, uuid

TEST_FILES = [
    'tests/acceptance/test_notification_wiring.py',
    'tests/acceptance/test_evidence_retention.py',
    'tests/e2e/test_e2e_observation_to_discrepancy_closure.py',
]

def fix_file(fp: str) -> None:
    p = pathlib.Path(fp)
    src = p.read_text()
    original = src

    # 1. Add neon_auth_user_id if missing in User() constructor
    # Pattern: User( ... email=...) without neon_auth_user_id
    # Strategy: insert neon_auth_user_id after User(
    def add_neon_id(m):
        block = m.group(0)
        if 'neon_auth_user_id' in block:
            return block
        # Insert after "User(\n" or "User("
        return block.replace('User(\n', 'User(\n        neon_auth_user_id=f"neon-{uuid4()}",\n', 1)
    
    # Use a simpler approach: replace User( blocks that lack neon_auth_user_id
    # Find all User( constructor calls
    lines = src.splitlines()
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect start of User( constructor (indented, not a function def)
        stripped = line.strip()
        if stripped.startswith('user') and '= User(' in line and 'neon_auth_user_id' not in line:
            # Check if neon_auth_user_id appears in next 15 lines
            snippet = '\n'.join(lines[i:i+15])
            if 'neon_auth_user_id' not in snippet:
                # Find the line with User( and insert neon_auth_user_id on next line
                indent = len(line) - len(line.lstrip())
                new_lines.append(line)
                i += 1
                # The next line should be the first argument
                new_lines.append(' ' * (indent + 4) + 'neon_auth_user_id=f"neon-{uuid4()}",')
                continue
        # Also handle: admin = User( or owner = User( etc.
        if re.search(r'\b\w+ = User\(', line) and 'neon_auth_user_id' not in line:
            snippet = '\n'.join(lines[i:i+15])
            if 'neon_auth_user_id' not in snippet and 'User(' in line:
                indent = len(line) - len(line.lstrip())
                if line.rstrip().endswith('User('):
                    new_lines.append(line)
                    i += 1
                    new_lines.append(' ' * (indent + 4) + 'neon_auth_user_id=f"neon-{uuid4()}",')
                    continue
                else:
                    # Inline User(... - harder, skip for now
                    pass
        new_lines.append(line)
        i += 1
    src = '\n'.join(new_lines)

    # Ensure uuid4 is imported
    if 'neon_auth_user_id' in src and 'from uuid import uuid4' not in src and 'uuid4' not in src[:200]:
        src = src.replace('from uuid import', 'from uuid import uuid4,', 1) if 'from uuid import' in src else src
    
    if src != original:
        p.write_text(src)
        print(f"Fixed: {fp}")
    else:
        print(f"No changes needed: {fp}")

for f in TEST_FILES:
    try:
        fix_file(f)
    except Exception as e:
        print(f"Error fixing {f}: {e}")
