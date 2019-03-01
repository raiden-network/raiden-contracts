import random
from typing import Callable

import pytest
from eth_utils import denoms, is_address

from raiden_contracts.tests.utils.constants import MAX_UINT256
from raiden_contracts.utils.signature import private_key_to_address


@pytest.fixture
def get_random_privkey() -> Callable:
    """Returns a random private key"""
    return lambda: "0x%064x" % random.randint(
        1,
        MAX_UINT256,
    )


@pytest.fixture
def get_random_address(get_random_privkey) -> Callable:
    """Returns a random valid ethereum address"""
    def f():
        return private_key_to_address(get_random_privkey())
    return f


@pytest.fixture(scope='session')
def faucet_private_key():
    """Returns private key of a faucet used in tests"""
    return '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'


@pytest.fixture(scope='session')
def faucet_address(faucet_private_key):
    """Returns address of a faucet used in tests"""
    return private_key_to_address(faucet_private_key)


@pytest.fixture(scope='session')
def contract_deployer_address(faucet_address):
    """Returns address of the contract deployer used in tests"""
    return faucet_address


@pytest.fixture
def send_funds(
    ethereum_tester,
    custom_token,
    faucet_address,
):
    """Send some tokens and eth to specified address."""
    def f(target: str):
        assert is_address(target)
        ethereum_tester.send_transaction({
            'from': faucet_address,
            'to': target,
            'gas': 21000,
            'value': 1 * denoms.ether,  # pylint: disable=E1101
        })
        custom_token.functions.transfer(
            target,
            10000,
        ).transact({'from': faucet_address})
    return f
