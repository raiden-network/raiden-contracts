import pytest
from raiden_contracts.contract_manager import ContractManager, CONTRACTS_SOURCE_DIRS


@pytest.fixture
def contracts_manager():
    return ContractManager(CONTRACTS_SOURCE_DIRS)
