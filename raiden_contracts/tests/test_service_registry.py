import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import CONTRACTS_VERSION


def test_deposit(service_registry, custom_token, get_accounts):
    (A,) = get_accounts(1)
    custom_token.functions.mint(10).call_and_transact({"from": A})
    custom_token.functions.approve(service_registry.address, 10).call_and_transact({"from": A})

    # happy path
    service_registry.functions.deposit(10).call_and_transact({"from": A})
    assert service_registry.functions.deposits(A).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 0

    # custom_token does not allow transfer of more tokens
    with pytest.raises(TransactionFailed):
        service_registry.functions.deposit(1).call({"from": A})


def test_setURL(service_registry, get_accounts):
    (A,) = get_accounts(1)
    url1 = "http://example.com"
    url2 = "http://raiden.example.com"

    # First setHost call, should add to `service_addresses`
    service_registry.functions.setURL(url1).call_and_transact({"from": A})
    assert service_registry.functions.urls(A).call() == url1
    assert service_registry.functions.service_addresses(0).call() == A
    assert service_registry.functions.serviceCount().call() == 1
    with pytest.raises(TransactionFailed):
        assert service_registry.functions.service_addresses(1).call()

    # Setting the host for the second time must not add the service address a
    # second time.
    service_registry.functions.setURL(url2).call_and_transact({"from": A})
    assert service_registry.functions.urls(A).call() == url2
    assert service_registry.functions.service_addresses(0).call() == A
    assert service_registry.functions.serviceCount().call() == 1


def test_version(service_registry):
    """ Check the result of contract_version() call on the ServiceRegistry """
    version = service_registry.functions.contract_version().call()
    assert version == CONTRACTS_VERSION
