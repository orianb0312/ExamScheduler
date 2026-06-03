import os
import ast
from pathlib import Path

# Define the root of the source code directory dynamically based on this test file's location.
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# A list of modules that are strictly forbidden in a standalone application.
# This prevents developers from accidentally turning the app into a client-server model.
FORBIDDEN_MODULES = {
    "requests", "flask", "fastapi", "django", "urllib",
    "http.client", "socket", "aiohttp", "httpx"
}


def test_no_network_or_server_imports():
    """
    Scans all Python files in the src directory to ensure no
    client-server or HTTP communication libraries are imported.
    """
    violating_files = []

    # Safe guard: if the src directory doesn't exist yet, just skip.
    if not SRC_DIR.exists():
        return

        # Recursively walk through all folders and files in the 'src' directory.
    for root, _, files in os.walk(SRC_DIR):
        for file in files:
            # We only care about Python source code files.
            if file.endswith(".py"):
                file_path = Path(root) / file

                # Open and read the file content.
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        # Parse the code into an Abstract Syntax Tree (AST).
                        # This allows us to analyze the code structure without actually executing it.
                        tree = ast.parse(f.read(), filename=str(file_path))
                    except SyntaxError:
                        # If a file has a syntax error, skip it (other tests will catch syntax issues).
                        continue

                        # Traverse the AST nodes looking for 'import' or 'from ... import ...' statements.
                for node in ast.walk(tree):
                    # Check standard imports (e.g., 'import requests')
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            # Split by '.' to catch submodules (e.g., 'urllib.request' -> 'urllib')
                            if alias.name.split('.')[0] in FORBIDDEN_MODULES:
                                violating_files.append((file.name, alias.name))

                    # Check 'from' imports (e.g., 'from flask import Flask')
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.split('.')[0] in FORBIDDEN_MODULES:
                            violating_files.append((file.name, node.module))

    # The test passes only if the violating_files list is empty.
    # Otherwise, it fails and prints exactly which files broke the architecture rule.
    assert not violating_files, (
        f"Architecture Violation: Found forbidden network/server imports: {violating_files}. "
        f"Version 2.0 must be a standalone offline application."
    )