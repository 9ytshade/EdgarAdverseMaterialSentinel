"""Windows compatibility, SDK path resolution, and contract reloader for genlayer-test direct mode."""

import atexit
import os
from pathlib import Path
import sys
import tempfile
import importlib.util
import pytest

# 1. Custom MetaPathFinder ensuring genlayer imports resolve to the cached stdlib
_cache_base = Path.home() / ".cache" / "gltest-direct" / "extracted"
_std_candidates = list(_cache_base.glob("**/py-lib-genlayer-std/*"))

if _std_candidates:
    _chosen_std = Path(_std_candidates[0])

    class GenLayerFinder:
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            if fullname == "genlayer" or fullname.startswith("genlayer."):
                subpath = fullname.replace(".", "/")
                target_init = _chosen_std / subpath / "__init__.py"
                target_py = _chosen_std / f"{subpath}.py"
                if target_init.exists():
                    return importlib.util.spec_from_file_location(
                        fullname,
                        target_init,
                        submodule_search_locations=[str(target_init.parent)],
                    )
                elif target_py.exists():
                    return importlib.util.spec_from_file_location(fullname, target_py)
            return None

    if not any(isinstance(f, type) and f.__name__ == "GenLayerFinder" for f in sys.meta_path):
        sys.meta_path.insert(0, GenLayerFinder)

    # Evict any existing shadowed module
    for k in list(sys.modules.keys()):
        if k == "genlayer" or k.startswith("genlayer."):
            del sys.modules[k]

# 2. Windows tempfile deferral for genlayer-test direct mode
if os.name == "nt":
    _orig_unlink = os.unlink
    _deferred_paths: list[str] = []

    def _safe_unlink(path, *args, **kwargs):
        try:
            _orig_unlink(path, *args, **kwargs)
        except (PermissionError, FileNotFoundError):
            _deferred_paths.append(str(path))

    os.unlink = _safe_unlink

    @atexit.register
    def _cleanup_deferred():
        for p in _deferred_paths:
            try:
                _orig_unlink(p)
            except Exception:
                pass

# 3. Reset __known_contract__ between test runs for clean test isolation
@pytest.fixture(autouse=True)
def reset_contract_registry():
    yield
    if "genlayer.gl.genvm_contracts" in sys.modules:
        sys.modules["genlayer.gl.genvm_contracts"].__known_contract__ = None
