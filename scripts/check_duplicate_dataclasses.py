#!/usr/bin/env python3
"""Script to detect duplicate dataclass definitions across the codebase.

This script scans Python files for @dataclass decorators and identifies
dataclasses with the same name defined in multiple locations, which can
lead to type drift and maintenance issues.

Usage:
    python scripts/check_duplicate_dataclasses.py

Exit codes:
    0 - No duplicates found
    1 - Duplicates detected
"""

import ast
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DataclassDefinition:
    """Information about a dataclass definition."""
    name: str
    file_path: Path
    line_number: int
    fields: list[str]


def extract_dataclasses(file_path: Path) -> list[DataclassDefinition]:
    """Extract all dataclass definitions from a Python file.
    
    Args:
        file_path: Path to the Python file to analyze
        
    Returns:
        List of DataclassDefinition objects found in the file
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return []
    
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    
    dataclasses = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if class has @dataclass decorator
            has_dataclass_decorator = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == 'dataclass':
                    has_dataclass_decorator = True
                    break
            
            if has_dataclass_decorator:
                # Extract field names
                fields = []
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        fields.append(item.target.id)
                
                dataclasses.append(DataclassDefinition(
                    name=node.name,
                    file_path=file_path,
                    line_number=node.lineno,
                    fields=fields
                ))
    
    return dataclasses


def find_all_python_files(root_dir: Path, exclude_dirs: set[str]) -> list[Path]:
    """Find all Python files in the directory tree.
    
    Args:
        root_dir: Root directory to search
        exclude_dirs: Set of directory names to exclude
        
    Returns:
        List of Python file paths
    """
    python_files = []
    
    for path in root_dir.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in exclude_dirs):
            continue
        python_files.append(path)
    
    return python_files


def detect_duplicates(dataclasses: list[DataclassDefinition]) -> dict[str, list[DataclassDefinition]]:
    """Group dataclasses by name to find duplicates.
    
    Args:
        dataclasses: List of all dataclass definitions
        
    Returns:
        Dictionary mapping dataclass names to their definitions (only includes duplicates)
    """
    by_name = defaultdict(list)
    
    for dc in dataclasses:
        by_name[dc.name].append(dc)
    
    # Filter to only duplicates (more than one definition)
    duplicates = {name: defs for name, defs in by_name.items() if len(defs) > 1}
    
    return duplicates


def main() -> int:
    """Main entry point for the script.
    
    Returns:
        Exit code (0 for success, 1 for duplicates found)
    """
    # Determine project root (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Directories to exclude from scanning
    exclude_dirs = {
        '__pycache__',
        '.pytest_cache',
        '.hypothesis',
        '.ruff_cache',
        'node_modules',
        '.venv',
        'venv',
        '.git',
        'marketpy.egg-info',
        'frontend',  # Exclude frontend (TypeScript/JavaScript)
        'build',
        'dist',
        'tests',
    }
    
    print(f"Scanning for dataclass definitions in: {project_root}")
    print(f"Excluding directories: {', '.join(sorted(exclude_dirs))}")
    print()
    
    # Find all Python files
    python_files = find_all_python_files(project_root, exclude_dirs)
    print(f"Found {len(python_files)} Python files to analyze")
    print()
    
    # Extract all dataclass definitions
    all_dataclasses = []
    for file_path in python_files:
        dataclasses = extract_dataclasses(file_path)
        all_dataclasses.extend(dataclasses)
    
    print(f"Found {len(all_dataclasses)} total dataclass definitions")
    print()
    
    # Detect duplicates
    duplicates = detect_duplicates(all_dataclasses)
    
    if not duplicates:
        print("✓ No duplicate dataclass definitions found!")
        return 0
    
    # Report duplicates
    print(f"✗ Found {len(duplicates)} duplicate dataclass name(s):")
    print()
    
    for name, definitions in sorted(duplicates.items()):
        print(f"Dataclass '{name}' defined in {len(definitions)} locations:")
        for defn in definitions:
            rel_path = defn.file_path.relative_to(project_root)
            print(f"  - {rel_path}:{defn.line_number}")
            if defn.fields:
                print(f"    Fields: {', '.join(defn.fields)}")
        print()
    
    print("Action required: Remove duplicate definitions and use a single canonical location.")
    print("Refer to backend/app/models/market.py for an example of canonical model definitions.")
    
    return 1


if __name__ == '__main__':
    sys.exit(main())
