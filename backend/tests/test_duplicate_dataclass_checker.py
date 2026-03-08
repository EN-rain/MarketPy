"""Tests for the duplicate dataclass detection script.

This test suite validates that the check_duplicate_dataclasses.py script
correctly identifies duplicate dataclass definitions across the codebase.
"""

# Import the functions from the script
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts'))

from check_duplicate_dataclasses import (
    DataclassDefinition,
    detect_duplicates,
    extract_dataclasses,
    find_all_python_files,
)


def test_extract_dataclasses_single():
    """Test extracting a single dataclass from a file."""
    code = '''from dataclasses import dataclass

@dataclass
class TestClass:
    field1: str
    field2: int
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = Path(f.name)

    try:
        dataclasses = extract_dataclasses(temp_path)

        assert len(dataclasses) == 1
        assert dataclasses[0].name == 'TestClass'
        assert dataclasses[0].file_path == temp_path
        assert dataclasses[0].line_number > 0  # Just verify line number is captured
        assert set(dataclasses[0].fields) == {'field1', 'field2'}
    finally:
        temp_path.unlink()


def test_extract_dataclasses_multiple():
    """Test extracting multiple dataclasses from a file."""
    code = '''
from dataclasses import dataclass

@dataclass
class FirstClass:
    name: str

@dataclass
class SecondClass:
    value: int
    active: bool
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = Path(f.name)

    try:
        dataclasses = extract_dataclasses(temp_path)

        assert len(dataclasses) == 2
        names = {dc.name for dc in dataclasses}
        assert names == {'FirstClass', 'SecondClass'}

        first = next(dc for dc in dataclasses if dc.name == 'FirstClass')
        assert first.fields == ['name']

        second = next(dc for dc in dataclasses if dc.name == 'SecondClass')
        assert set(second.fields) == {'value', 'active'}
    finally:
        temp_path.unlink()


def test_extract_dataclasses_no_dataclass():
    """Test that regular classes without @dataclass are ignored."""
    code = '''
class RegularClass:
    def __init__(self):
        self.field = "value"

class AnotherClass:
    pass
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = Path(f.name)

    try:
        dataclasses = extract_dataclasses(temp_path)
        assert len(dataclasses) == 0
    finally:
        temp_path.unlink()


def test_extract_dataclasses_mixed():
    """Test extracting dataclasses when mixed with regular classes."""
    code = '''
from dataclasses import dataclass

class RegularClass:
    pass

@dataclass
class DataClass:
    field: str

class AnotherRegular:
    pass
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = Path(f.name)

    try:
        dataclasses = extract_dataclasses(temp_path)

        assert len(dataclasses) == 1
        assert dataclasses[0].name == 'DataClass'
    finally:
        temp_path.unlink()


def test_detect_duplicates_none():
    """Test duplicate detection when there are no duplicates."""
    dataclasses = [
        DataclassDefinition('ClassA', Path('file1.py'), 10, ['field1']),
        DataclassDefinition('ClassB', Path('file2.py'), 20, ['field2']),
        DataclassDefinition('ClassC', Path('file3.py'), 30, ['field3']),
    ]

    duplicates = detect_duplicates(dataclasses)
    assert len(duplicates) == 0


def test_detect_duplicates_single():
    """Test duplicate detection with one duplicate name."""
    dataclasses = [
        DataclassDefinition('ClassA', Path('file1.py'), 10, ['field1']),
        DataclassDefinition('ClassB', Path('file2.py'), 20, ['field2']),
        DataclassDefinition('ClassA', Path('file3.py'), 30, ['field3']),
    ]

    duplicates = detect_duplicates(dataclasses)

    assert len(duplicates) == 1
    assert 'ClassA' in duplicates
    assert len(duplicates['ClassA']) == 2

    paths = {dc.file_path for dc in duplicates['ClassA']}
    assert paths == {Path('file1.py'), Path('file3.py')}


def test_detect_duplicates_multiple():
    """Test duplicate detection with multiple duplicate names."""
    dataclasses = [
        DataclassDefinition('ClassA', Path('file1.py'), 10, ['field1']),
        DataclassDefinition('ClassB', Path('file2.py'), 20, ['field2']),
        DataclassDefinition('ClassA', Path('file3.py'), 30, ['field3']),
        DataclassDefinition('ClassB', Path('file4.py'), 40, ['field4']),
        DataclassDefinition('ClassC', Path('file5.py'), 50, ['field5']),
    ]

    duplicates = detect_duplicates(dataclasses)

    assert len(duplicates) == 2
    assert 'ClassA' in duplicates
    assert 'ClassB' in duplicates
    assert 'ClassC' not in duplicates

    assert len(duplicates['ClassA']) == 2
    assert len(duplicates['ClassB']) == 2


def test_detect_duplicates_triple():
    """Test duplicate detection with three instances of the same name."""
    dataclasses = [
        DataclassDefinition('Duplicate', Path('file1.py'), 10, ['field1']),
        DataclassDefinition('Duplicate', Path('file2.py'), 20, ['field2']),
        DataclassDefinition('Duplicate', Path('file3.py'), 30, ['field3']),
    ]

    duplicates = detect_duplicates(dataclasses)

    assert len(duplicates) == 1
    assert 'Duplicate' in duplicates
    assert len(duplicates['Duplicate']) == 3


def test_find_all_python_files():
    """Test finding Python files while excluding certain directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create directory structure
        (root / 'src').mkdir()
        (root / 'tests').mkdir()
        (root / '__pycache__').mkdir()
        (root / 'node_modules').mkdir()

        # Create Python files
        (root / 'main.py').touch()
        (root / 'src' / 'module.py').touch()
        (root / 'tests' / 'test_module.py').touch()
        (root / '__pycache__' / 'cached.py').touch()
        (root / 'node_modules' / 'package.py').touch()

        # Find files excluding __pycache__ and node_modules
        exclude_dirs = {'__pycache__', 'node_modules'}
        python_files = find_all_python_files(root, exclude_dirs)

        # Convert to relative paths for easier comparison
        rel_paths = {f.relative_to(root) for f in python_files}

        assert Path('main.py') in rel_paths
        assert Path('src/module.py') in rel_paths
        assert Path('tests/test_module.py') in rel_paths
        assert Path('__pycache__/cached.py') not in rel_paths
        assert Path('node_modules/package.py') not in rel_paths


def test_extract_dataclasses_with_default_values():
    """Test extracting dataclasses with default field values."""
    code = '''
from dataclasses import dataclass

@dataclass
class ConfigClass:
    name: str
    value: int = 10
    active: bool = True
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = Path(f.name)

    try:
        dataclasses = extract_dataclasses(temp_path)

        assert len(dataclasses) == 1
        assert dataclasses[0].name == 'ConfigClass'
        assert set(dataclasses[0].fields) == {'name', 'value', 'active'}
    finally:
        temp_path.unlink()


def test_extract_dataclasses_empty():
    """Test extracting dataclasses with no fields."""
    code = '''
from dataclasses import dataclass

@dataclass
class EmptyClass:
    pass
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = Path(f.name)

    try:
        dataclasses = extract_dataclasses(temp_path)

        assert len(dataclasses) == 1
        assert dataclasses[0].name == 'EmptyClass'
        assert dataclasses[0].fields == []
    finally:
        temp_path.unlink()


def test_no_duplicates_in_actual_codebase():
    """Integration test: verify no duplicates exist in the actual codebase."""
    # This test runs against the real codebase
    project_root = Path(__file__).parent.parent.parent

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
        'frontend',
        'build',
        'dist',
        'tests',
    }

    python_files = find_all_python_files(project_root, exclude_dirs)

    all_dataclasses = []
    for file_path in python_files:
        dataclasses = extract_dataclasses(file_path)
        all_dataclasses.extend(dataclasses)

    duplicates = detect_duplicates(all_dataclasses)

    # This should pass since we've already removed duplicates in task 3.2
    assert len(duplicates) == 0, (
        f"Found duplicate dataclasses: {list(duplicates.keys())}. "
        "Run 'python scripts/check_duplicate_dataclasses.py' for details."
    )
