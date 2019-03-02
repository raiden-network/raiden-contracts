import pytest
from raiden_contracts.contract_manager import ContractManager, contracts_source_path


@pytest.fixture
def contracts_manager():
    return ContractManager(contracts_source_path())
