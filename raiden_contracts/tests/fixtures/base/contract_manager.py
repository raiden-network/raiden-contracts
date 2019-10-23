from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator

import pytest

from raiden_contracts.contract_source_manager import ContractSourceManager, contracts_source_path


@pytest.fixture(scope="session")
def contract_source_manager() -> ContractSourceManager:
    return ContractSourceManager(contracts_source_path(contracts_version=None))


@pytest.fixture(scope="session")
def contracts_manager(contract_source_manager: ContractSourceManager) -> Generator:
    with NamedTemporaryFile() as target_path:
        yield contract_source_manager.compile_contracts(Path(target_path.name))
