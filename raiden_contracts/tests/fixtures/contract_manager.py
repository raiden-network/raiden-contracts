import pytest
from raiden_contracts.contract_manager import CONTRACT_MANAGER


@pytest.fixture
def contracts_manager():
    return CONTRACT_MANAGER
