#!/usr/bin/env python3
"""Validate imports match the Docker environment structure."""

import os
import re
import sys

def check_file_imports(filepath):
    """Check imports in a Python file."""
    issues = []
    
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Find all imports
    import_pattern = r'^(from|import)\s+([^\s]+)'
    
    for line_num, line in enumerate(content.split('\n'), 1):
        match = re.match(import_pattern, line.strip())
        if match:
            import_type, import_path = match.groups()
            
            # Check relative imports
            if import_type == 'from' and import_path.startswith('..'):
                # Count the dots to understand the relative level
                dots = len(import_path) - len(import_path.lstrip('.'))
                remainder = import_path[dots:]
                
                # Validate based on file location
                if 'services/knowledge/' in filepath:
                    if dots == 2:  # .. imports
                        valid_modules = ['storage', 'rag', 'credential_service', 'source_summary_service']
                        module = remainder.split('.')[0] if remainder else ''
                        if module and module not in valid_modules:
                            issues.append(f"Line {line_num}: Invalid module '{module}' for .. import")
                    elif dots == 3:  # ... imports
                        valid_modules = ['config', 'utils', 'agents']
                        module = remainder.split('.')[0] if remainder else ''
                        if module and module not in valid_modules:
                            issues.append(f"Line {line_num}: Invalid module '{module}' for ... import")
                            
                elif 'fastapi/' in filepath:
                    if dots == 2:  # .. imports
                        valid_modules = ['services', 'utils', 'config', 'socketio_app']
                        module = remainder.split('.')[0] if remainder else ''
                        if module and module not in valid_modules:
                            issues.append(f"Line {line_num}: Invalid module '{module}' for .. import")
    
    return issues

def main():
    """Check all relevant files."""
    base_path = '/Users/sean/Software/archon-2/python/src/server'
    
    files_to_check = [
        'fastapi/knowledge_api.py',
        'services/knowledge/crawl_orchestration_service.py',
        'services/knowledge/knowledge_item_service.py',
        'services/knowledge/code_extraction_service.py',
        'services/knowledge/database_metrics_service.py',
    ]
    
    all_issues = []
    
    for file_path in files_to_check:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            issues = check_file_imports(full_path)
            if issues:
                all_issues.append((file_path, issues))
    
    if all_issues:
        print("Import issues found:\n")
        for file_path, issues in all_issues:
            print(f"{file_path}:")
            for issue in issues:
                print(f"  {issue}")
            print()
    else:
        print("All imports look correct!")

if __name__ == "__main__":
    main()