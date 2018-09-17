import pytest
from raiden_contracts.contract_manager import CONTRACTS_SOURCE_DIRS, ContractManager


@pytest.fixture
def contracts_manager():
    return ContractManager(CONTRACTS_SOURCE_DIRS)
