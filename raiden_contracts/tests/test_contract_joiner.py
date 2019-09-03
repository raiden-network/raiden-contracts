from tempfile import NamedTemporaryFile

import pytest

from raiden_contracts.utils.join_contracts import ContractJoiner


def test_contract_joiner_with_non_existent_file() -> None:
    """ Using ContractJoiner on a source importing a nonexistent file """
    joiner = ContractJoiner()
    source_with_missing_import = """
        import "NonExistent.sol";
    """
    with NamedTemporaryFile() as source_file:
        source_file.write(bytearray(source_with_missing_import, "ascii"))
        source_file.flush()
        with pytest.raises(FileNotFoundError):
            joiner.join(open(source_file.name))
