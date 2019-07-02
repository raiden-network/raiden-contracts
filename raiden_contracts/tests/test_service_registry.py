from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3.contract import Contract

from raiden_contracts.tests.utils.constants import CONTRACT_DEPLOYER_ADDRESS


def test_owner_of_service_registry(service_registry: Contract) -> None:
    """ The owner of ServiceRegistry should be the deployer """
    assert service_registry.functions.owner().call() == CONTRACT_DEPLOYER_ADDRESS


def test_setURL(service_registry: Contract, get_accounts: Callable) -> None:
    (A,) = get_accounts(1)
    url = "http://example.com"

    # Register A as a service
    service_registry.functions.add_service(A).call_and_transact(
        {"from": CONTRACT_DEPLOYER_ADDRESS}
    )
    assert service_registry.functions.is_service(A).call()

    # A sets a URL
    service_registry.functions.setURL(url).call_and_transact({"from": A})
    assert service_registry.functions.urls(A).call() == url
