from typing import Callable

import pytest
from eth_tester import EthereumTester
from eth_utils import is_address
from eth_utils.units import units
from web3.contract import Contract

from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.tests.utils.constants import FAUCET_ADDRESS


@pytest.fixture
def send_funds(ethereum_tester: EthereumTester, custom_token: Contract) -> Callable:
    """Send some tokens and eth to specified address."""

    def f(target: str) -> None:
        assert is_address(target)
        ethereum_tester.send_transaction(
            {
                "from": FAUCET_ADDRESS,
                "to": target,
                "gas": 21000,
                "value": 1 * int(units["ether"]),
            }
        )
        call_and_transact(
            custom_token.functions.transfer(_to=target, _value=10000),
            {"from": FAUCET_ADDRESS},
        )

    return f
