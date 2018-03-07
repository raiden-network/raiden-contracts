import pytest
from ethereum import tester
from tests.fixtures.utils import *
from tests.fixtures.token_network import *


def test_version(token_network):
    assert token_network.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_constructor():
    pass


def test_events(token_network_registry, event_handler):
    pass


def test_print_gas_cost(token_network_registry, print_gas):
    pass
