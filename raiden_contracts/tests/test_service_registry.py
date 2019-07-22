from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract, get_event_data

from raiden_contracts.constants import (
    CONTRACT_SERVICE_REGISTRY,
    EMPTY_ADDRESS,
    EVENT_REGISTERED_SERVICE,
)
from raiden_contracts.contract_manager import ContractManager, contracts_precompiled_path
from raiden_contracts.tests.utils.constants import (
    CONTRACT_DEPLOYER_ADDRESS,
    DEFAULT_BUMP_DENOMINATOR,
    DEFAULT_BUMP_NUMERATOR,
    DEFAULT_DECAY_CONSTANT,
    DEFAULT_REGISTRATION_DURATION,
    DEFAULT_MIN_PRICE,
    SECONDS_PER_DAY,
    SERVICE_DEPOSIT,
    UINT256_MAX,
)


def test_deposit_contract(
    get_deposit_contract: Callable, custom_token: Contract, get_accounts: Callable
) -> None:
    (A,) = get_accounts(1)
    custom_token.functions.mint(100).call_and_transact({"from": A})
    depo = get_deposit_contract([custom_token.address, 0, A])
    custom_token.functions.transfer(depo.address, 100).call_and_transact({"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100
    depo.functions.withdraw(A).call_and_transact({"from": A})
    assert custom_token.functions.balanceOf(A).call() == 100
    assert custom_token.functions.balanceOf(depo.address).call() == 0


def test_deposit_contract_too_early_withdraw(
    get_deposit_contract: Callable, custom_token: Contract, get_accounts: Callable
) -> None:
    (A,) = get_accounts(1)
    custom_token.functions.mint(100).call_and_transact({"from": A})
    depo = get_deposit_contract([custom_token.address, UINT256_MAX, A])
    custom_token.functions.transfer(depo.address, 100).call_and_transact({"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100
    with pytest.raises(TransactionFailed):
        depo.functions.withdraw(A).call_and_transact({"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100


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
    first_expiration = service_registry.functions.service_valid_till(A).call()

    # custom_token does not allow transfer of more tokens
    with pytest.raises(TransactionFailed):
        service_registry.functions.deposit(1).call({"from": A})

    # More minting and approving before extending the registration
    custom_token.functions.mint(SERVICE_DEPOSIT).call_and_transact({"from": A})
    custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT).call_and_transact(
        {"from": A}
    )

    # Extending the registration
    service_registry.functions.deposit(SERVICE_DEPOSIT).call_and_transact({"from": A})
    second_expiration = service_registry.functions.service_valid_till(A).call()
    assert second_expiration == first_expiration + DEFAULT_REGISTRATION_DURATION


def test_setURL(
    custom_token: Contract, service_registry: Contract, get_accounts: Callable, web3: Web3
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
    contract_manager = ContractManager(contracts_precompiled_path(version=None))
    event_abi = contract_manager.get_event_abi(CONTRACT_SERVICE_REGISTRY, EVENT_REGISTERED_SERVICE)
    event_data = get_event_data(event_abi, tx_receipt["logs"][-1])
    assert event_data["args"]["service"] == A
    assert event_data["args"]["deposit_contract"] != EMPTY_ADDRESS

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


def test_changing_duration(
    service_registry: Contract, get_accounts: Callable, custom_token: Contract
) -> None:
    new_duration = 90 * SECONDS_PER_DAY
    service_registry.functions.change_parameters(
        _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
        _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
        _decay_constant=DEFAULT_DECAY_CONSTANT,
        _min_price=DEFAULT_MIN_PRICE,
        _registration_duration=new_duration,
    ).call_and_transact({"from": CONTRACT_DEPLOYER_ADDRESS})
    assert service_registry.functions.registration_duration().call() == new_duration
    # make sure that the duration has changed.
    (A,) = get_accounts(1)
    custom_token.functions.mint(2 * SERVICE_DEPOSIT).call_and_transact({"from": A})
    custom_token.functions.approve(
        service_registry.address, 2 * SERVICE_DEPOSIT
    ).call_and_transact({"from": A})
    service_registry.functions.deposit(SERVICE_DEPOSIT).call_and_transact({"from": A})
    first_expiration = service_registry.functions.service_valid_till(A).call()
    service_registry.functions.deposit(SERVICE_DEPOSIT).call_and_transact({"from": A})
    second_expiration = service_registry.functions.service_valid_till(A).call()
    assert second_expiration == first_expiration + new_duration


def test_changing_bump_numerator(service_registry: Contract) -> None:
    service_registry.functions.change_parameters(
        _price_bump_numerator=DEFAULT_BUMP_NUMERATOR + 1,
        _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
        _decay_constant=DEFAULT_DECAY_CONSTANT,
        _min_price=DEFAULT_MIN_PRICE,
        _registration_duration=DEFAULT_REGISTRATION_DURATION,
    ).call_and_transact({"from": CONTRACT_DEPLOYER_ADDRESS})
    assert service_registry.functions.price_bump_numerator().call() == DEFAULT_BUMP_NUMERATOR + 1
