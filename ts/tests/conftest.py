"""Cross-test cleanup for third-party runners that temporarily replace __main__."""
from __future__ import annotations

import sys

import pytest

_INITIAL_MAIN = sys.modules.get("__main__")
_MISSING = object()
_INITIAL_FILE = getattr(_INITIAL_MAIN, "__file__", _MISSING)
_INITIAL_SPEC = getattr(_INITIAL_MAIN, "__spec__", _MISSING)


@pytest.fixture(autouse=True)
def restore_main_module_identity():
    """Keep Streamlit AppTest from changing multiprocessing's spawn target."""
    yield
    if _INITIAL_MAIN is None:
        return
    sys.modules["__main__"] = _INITIAL_MAIN
    for name, value in (("__file__", _INITIAL_FILE), ("__spec__", _INITIAL_SPEC)):
        if value is _MISSING:
            try:
                delattr(_INITIAL_MAIN, name)
            except AttributeError:
                pass
        else:
            setattr(_INITIAL_MAIN, name, value)
