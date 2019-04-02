import pytest
from eth_utils import denoms, is_address

from raiden_contracts.tests.utils.constants import FAUCET_ADDRESS


@pytest.fixture
def send_funds(
        ethereum_tester,
        custom_token,
):
    """Send some tokens and eth to specified address."""
    def f(target: str):
        assert is_address(target)
        ethereum_tester.send_transaction({
            'from': FAUCET_ADDRESS,
            'to': target,
            'gas': 21000,
            'value': 1 * denoms.ether,  # pylint: disable=E1101
        })
        custom_token.functions.transfer(
            target,
            10000,
        ).call_and_transact({'from': FAUCET_ADDRESS})
    return f
