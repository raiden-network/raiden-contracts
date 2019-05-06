import pytest

from raiden_contracts.contract_manager import contracts_precompiled_path
from raiden_contracts.contract_source_manager import ContractSourceManager, contracts_source_path


@pytest.fixture(scope="session")
def contract_source_manager():
    return ContractSourceManager(contracts_source_path())


@pytest.fixture(scope="session")
def contracts_manager(contract_source_manager):
    return contract_source_manager.compile_contracts(contracts_precompiled_path())
