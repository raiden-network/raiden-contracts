import tempfile
from pathlib import Path

import pytest

from raiden_contracts.utils.file_ops import load_json_from_path


def test_load_json_from_corrupt_file() -> None:
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"not a JSON")
        with pytest.raises(ValueError):
            load_json_from_path(Path(f.name))
