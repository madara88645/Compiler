import pytest
from app import get_version, __version__

def test_get_version():
    version = get_version()
    assert isinstance(version, str)
    assert len(version) > 0
    assert version == __version__
