import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import CONTRACTS_VERSION


def test_deposit(
    service_registry,
    custom_token,
    get_accounts,
):
    (A, ) = get_accounts(1)
    custom_token.functions.mint(10).transact({'from': A})
    custom_token.functions.approve(service_registry.address, 10).transact({'from': A})

    # happy path
    service_registry.functions.deposit(10).transact({'from': A})
    assert service_registry.functions.deposits(A).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 0

    # custom_token does not allow transfer of more tokens
    with pytest.raises(TransactionFailed):
        service_registry.functions.deposit(1).transact({'from': A})


def test_version(service_registry):
    """ Check the result of contract_version() call on the ServiceRegistry """
    version = service_registry.functions.contract_version().call()
    assert version == CONTRACTS_VERSION
