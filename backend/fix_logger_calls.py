"""
Script to fix all logger calls to use f-strings instead of keyword arguments.
This is needed because we replaced structlog with Python's standard logging.
"""
import re
import os
from pathlib import Path

def fix_logger_call(match):
    """Convert logger call with kwargs to f-string format."""
    indent = match.group(1)
    log_level = match.group(2)
    content = match.group(3)

    # Skip if already using f-string
    if content.strip().startswith('f"') or content.strip().startswith("f'"):
        return match.group(0)

    # Skip simple string-only calls
    if '=' not in content:
        return match.group(0)

    # Extract message and kwargs
    lines = content.split('\n')
    parts = []
    for line in lines:
        line = line.strip()
        if line and line != ',':
            parts.append(line)

    if not parts:
        return match.group(0)

    # First part is usually the message
    message = parts[0].strip(',').strip('"').strip("'")

    # Rest are kwargs
    kwargs = []
    for part in parts[1:]:
        part = part.strip(',')
        if '=' in part:
            kwargs.append(part)

    if not kwargs:
        return match.group(0)

    # Build f-string
    kwargs_str = ', '.join(kwargs)
    new_call = f'{indent}logger.{log_level}(\n{indent}    f"{message} - {kwargs_str}"\n{indent})'

    return new_call


def fix_file(filepath):
    """Fix all logger calls in a file."""
    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content

    # Pattern to match logger calls with multiple lines
    pattern = r'(\s+)logger\.(info|error|warning|debug)\(\s*\n(.*?)\n\s*\)'
    content = re.sub(pattern, fix_logger_call, content, flags=re.DOTALL)

    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False


def main():
    """Fix all Python files in the backend directory."""
    backend_dir = Path('/Users/I758002/dinnr-singhacks/backend')

    # Files to fix
    files_to_check = [
        'agents/aml_monitoring/payment_analysis_agent.py',
        'agents/aml_monitoring/verdict_router.py',
        'agents/aml_monitoring/rule_checker_agent.py',
        'agents/aml_monitoring/risk_analyzer.py',
        'services/audit_service.py',
        'services/alert_service.py',
        'services/verdict_service.py',
        'services/history_service.py',
        'services/rules_service.py',
    ]

    fixed_count = 0
    for file_path in files_to_check:
        full_path = backend_dir / file_path
        if full_path.exists():
            print(f"Checking {file_path}...")
            if fix_file(full_path):
                print(f"  ✓ Fixed {file_path}")
                fixed_count += 1
            else:
                print(f"  - No changes needed for {file_path}")
        else:
            print(f"  ✗ File not found: {file_path}")

    print(f"\nFixed {fixed_count} files")


if __name__ == '__main__':
    main()
