import tempfile
from pathlib import Path

import pytest

from raiden_contracts.contract_manager import _load_json_from_path


def test_load_json_from_corrupt_file():
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"not a JSON")
        with pytest.raises(ValueError):
            _load_json_from_path(Path(f.name))
