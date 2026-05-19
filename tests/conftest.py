import shutil
import uuid
from pathlib import Path

import pytest


class WorkspaceTempPathFactory:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def mktemp(self, basename: str, numbered: bool = True) -> Path:
        suffix = uuid.uuid4().hex[:10] if numbered else "fixed"
        path = self.root / f"{basename}_{suffix}"
        path.mkdir(parents=True, exist_ok=False)
        return path


@pytest.fixture(scope="session")
def tmp_path_factory():
    root = Path(__file__).resolve().parents[1] / ".pytest_work"
    factory = WorkspaceTempPathFactory(root)
    yield factory
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def tmp_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("test")
    yield path
    shutil.rmtree(path, ignore_errors=True)
