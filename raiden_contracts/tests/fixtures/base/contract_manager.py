from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from raiden_contracts.contract_source_manager import ContractSourceManager, contracts_source_path


@pytest.fixture(scope="session")
def contract_source_manager():
    return ContractSourceManager(contracts_source_path())


@pytest.fixture(scope="session")
def contracts_manager(contract_source_manager):
    target_path = NamedTemporaryFile()
    return contract_source_manager.compile_contracts(Path(target_path.name))
