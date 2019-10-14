from typing import Callable, Dict

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_DEPOSIT


@pytest.fixture
def get_deposit_contract(deploy_tester_contract: Callable) -> Callable:
    """Deploy a Deposit contract with the given arguments"""

    def get(**arguments: Dict) -> Contract:
        return deploy_tester_contract(CONTRACT_DEPOSIT, **arguments)

    return get
