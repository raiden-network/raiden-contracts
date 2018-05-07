import pytest
from raiden_contracts.contract_manager import ContractManager, CONTRACTS_SOURCE_DIRS


@pytest.fixture(scope='session')
def contracts_manager():
    return ContractManager(CONTRACTS_SOURCE_DIRS)
