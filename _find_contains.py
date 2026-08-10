"""Find all .contains() calls on roles column in non-test service files."""
import pathlib, os

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__')]
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        if 'test' in fp.lower():
            continue
        try:
            src = pathlib.Path(fp).read_text(errors='ignore')
        except Exception:
            continue
        for i, l in enumerate(src.splitlines(), 1):
            if '.contains(' in l and 'role' in l.lower():
                print(f"{fp}:{i}: {l.strip()}")
