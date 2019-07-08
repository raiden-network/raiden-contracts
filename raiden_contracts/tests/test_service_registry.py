from typing import Callable

import pytest
import web3
from eth_tester.exceptions import TransactionFailed
from web3.contract import Contract, get_event_data

from raiden_contracts.constants import CONTRACT_SERVICE_REGISTRY, EVENT_REGISTERED_SERVICE
from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils.constants import CONTRACT_DEPLOYER_ADDRESS, SERVICE_DEPOSIT


def test_owner_of_service_registry(service_registry: Contract) -> None:
    """ The owner of ServiceRegistry should be the deployer """
    assert service_registry.functions.owner().call() == CONTRACT_DEPLOYER_ADDRESS


def test_deposit(
    service_registry: Contract, custom_token: Contract, get_accounts: Callable
) -> None:
    (A,) = get_accounts(1)
    custom_token.functions.mint(SERVICE_DEPOSIT).call_and_transact({"from": A})
    custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT).call_and_transact(
        {"from": A}
    )

    # happy path
    old_balance = custom_token.functions.balanceOf(A).call()
    old_price = service_registry.functions.current_price().call()
    service_registry.functions.deposit(SERVICE_DEPOSIT).call_and_transact({"from": A})
    assert old_balance > custom_token.functions.balanceOf(A).call() > old_balance - old_price
    assert service_registry.functions.current_price().call() > old_price

    # custom_token does not allow transfer of more tokens
    with pytest.raises(TransactionFailed):
        service_registry.functions.deposit(1).call({"from": A})


def test_setURL(
    custom_token: Contract,
    service_registry: Contract,
    get_accounts: Callable,
    contract_manager: ContractManager,
) -> None:
    (A,) = get_accounts(1)
    url1 = "http://example.com"
    url2 = "http://raiden.example.com"

    custom_token.functions.mint(SERVICE_DEPOSIT).call_and_transact({"from": A})
    custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT).call_and_transact(
        {"from": A}
    )
    tx = service_registry.functions.deposit(SERVICE_DEPOSIT).call_and_transact({"from": A})
    tx_receipt = web3.eth.getTransactionReceipt(tx)
    event_abi = contract_manager.get_event_abi(CONTRACT_SERVICE_REGISTRY, EVENT_REGISTERED_SERVICE)
    event_data = get_event_data(event_abi, tx_receipt["logs"][0])
    assert event_data["args"][0] == A
    assert event_data["args"][3]

    service_registry.functions.setURL(url1).call_and_transact({"from": A})
    assert service_registry.functions.urls(A).call() == url1

    service_registry.functions.setURL(url2).call_and_transact({"from": A})
    assert service_registry.functions.urls(A).call() == url2


def test_decayed_price(service_registry: Contract) -> None:
    assert service_registry.functions.decayed_price(100000, 0).call() == 100000

    # The minimum price is 1000
    assert service_registry.functions.decayed_price(100, 0).call() == 1000

    # roughly 139 days till the price halves.
    assert service_registry.functions.decayed_price(100000, 11990300).call() == 50000
