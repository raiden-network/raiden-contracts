import pytest
from ethereum import tester
from utils.config import C_TOKEN_NETWORK_REGISTRY, E_TOKEN_NETWORK_CREATED
from tests.fixtures.utils import *
from tests.fixtures.token_network_registry import *


def test_version(token_network_registry):
    assert token_network_registry.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_secret_registry_address(token_network_registry, secret_registry):
    pass


def test_constructor():
    pass


def test_create_erc20_token_network_call(token_network_registry):
    pass


def test_create_erc20_token_network(token_network_registry):
    pass


def test_events(token_network_registry, event_handler):
    pass


def test_print_gas_cost(token_network_registry, print_gas):
    pass
