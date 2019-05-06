import pytest
from eth_utils import is_address
from eth_utils.units import units

from raiden_contracts.tests.utils.constants import FAUCET_ADDRESS


@pytest.fixture
def send_funds(ethereum_tester, custom_token):
    """Send some tokens and eth to specified address."""

    def f(target: str):
        assert is_address(target)
        ethereum_tester.send_transaction(
            {"from": FAUCET_ADDRESS, "to": target, "gas": 21000, "value": 1 * int(units["ether"])}
        )
        custom_token.functions.transfer(_to=target, _value=10000).call_and_transact(
            {"from": FAUCET_ADDRESS}
        )

    return f
