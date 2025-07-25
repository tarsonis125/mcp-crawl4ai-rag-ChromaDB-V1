#!/usr/bin/env python3
"""Fix import paths in test files"""
import os
import re

def fix_imports_in_file(filepath):
    """Fix imports in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace python.src. with src.
    original_content = content
    content = re.sub(r'from python\.src\.', 'from src.', content)
    content = re.sub(r'import python\.src\.', 'import src.', content)
    content = re.sub(r"'python\.src\.", "'src.", content)
    content = re.sub(r'"python\.src\.', '"src.', content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed imports in: {filepath}")
        return True
    return False

def main():
    """Fix all test files"""
    test_dir = "tests"
    fixed_count = 0
    
    for filename in os.listdir(test_dir):
        if filename.startswith("test_") and filename.endswith(".py"):
            filepath = os.path.join(test_dir, filename)
            if fix_imports_in_file(filepath):
                fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()