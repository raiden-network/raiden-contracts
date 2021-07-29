from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract, get_event_data
from web3.exceptions import MismatchedABI

from raiden_contracts.constants import (
    CONTRACT_DEPOSIT,
    CONTRACT_SERVICE_REGISTRY,
    EMPTY_ADDRESS,
    EVENT_REGISTERED_SERVICE,
)
from raiden_contracts.contract_manager import ContractManager, contracts_precompiled_path
from raiden_contracts.tests.utils import HexBytes, call_and_transact
from raiden_contracts.tests.utils.constants import (
    DEFAULT_BUMP_DENOMINATOR,
    DEFAULT_BUMP_NUMERATOR,
    DEFAULT_DECAY_CONSTANT,
    DEFAULT_MIN_PRICE,
    DEFAULT_REGISTRATION_DURATION,
    DEPLOYER_ADDRESS,
    SECONDS_PER_DAY,
    SERVICE_DEPOSIT,
    UINT256_MAX,
)


def test_deposit_contract(
    get_deposit_contract: Callable, custom_token: Contract, get_accounts: Callable
) -> None:
    """Deposit contract with zero-deadline should release the deposit immediately"""
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(100), {"from": A})
    depo = get_deposit_contract(
        _token=custom_token.address, _release_at=0, _withdrawer=A, _service_registry=A
    )
    call_and_transact(custom_token.functions.transfer(depo.address, 100), {"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100
    call_and_transact(depo.functions.withdraw(A), {"from": A})
    assert custom_token.functions.balanceOf(A).call() == 100
    assert custom_token.functions.balanceOf(depo.address).call() == 0


def test_deposit_contract_without_service_registry_code(
    get_deposit_contract: Callable, custom_token: Contract, get_accounts: Callable
) -> None:
    """If Deposit has no code in service registry, too early withdrawals fail"""
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(100), {"from": A})
    depo = get_deposit_contract(
        _token=custom_token.address,
        _release_at=UINT256_MAX,
        _withdrawer=A,
        _service_registry=A,
    )
    call_and_transact(custom_token.functions.transfer(depo.address, 100), {"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100
    # The call fails because an empty account doesn't return a boolean.
    # In this case, the message of the TransactionFailed exception is ''.
    with pytest.raises(TransactionFailed) as ex:
        call_and_transact(depo.functions.withdraw(A), {"from": A})
    assert str(ex.value) == "execution reverted: b''"

    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100


def test_deposit_contract_too_early_withdraw(
    get_deposit_contract: Callable,
    custom_token: Contract,
    get_accounts: Callable,
    service_registry: Contract,
) -> None:
    """Deposit contract with some deadline should not release the deposit immediately"""
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(100), {"from": A})
    depo = get_deposit_contract(
        _token=custom_token.address,
        _release_at=UINT256_MAX,
        _withdrawer=A,
        _service_registry=service_registry.address,
    )
    call_and_transact(custom_token.functions.transfer(depo.address, 100), {"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100
    with pytest.raises(TransactionFailed, match="deposit not released yet"):
        call_and_transact(depo.functions.withdraw(A), {"from": A})
    assert custom_token.functions.balanceOf(A).call() == 0
    assert custom_token.functions.balanceOf(depo.address).call() == 100


def test_deposit(
    service_registry: Contract, custom_token: Contract, get_accounts: Callable
) -> None:
    """A service provider can make deposits to ServiceRegistry"""
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(SERVICE_DEPOSIT), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT),
        {"from": A},
    )

    # happy path
    old_balance = custom_token.functions.balanceOf(A).call()
    old_price = service_registry.functions.currentPrice().call()
    old_len = service_registry.functions.everMadeDepositsLen().call()
    assert not service_registry.functions.hasValidRegistration(A).call()
    call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": A})
    assert old_balance > custom_token.functions.balanceOf(A).call() > old_balance - old_price
    assert service_registry.functions.currentPrice().call() > old_price
    assert service_registry.functions.everMadeDepositsLen().call() == old_len + 1
    assert service_registry.functions.hasValidRegistration(A).call()
    first_expiration = service_registry.functions.service_valid_till(A).call()

    # custom_token does not allow transfer of more tokens
    with pytest.raises(TransactionFailed, match="not enough limit"):
        service_registry.functions.deposit(1).call({"from": A})

    # More minting and approving before extending the registration
    call_and_transact(custom_token.functions.mint(SERVICE_DEPOSIT), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT),
        {"from": A},
    )

    # Extending the registration
    call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": A})
    assert service_registry.functions.hasValidRegistration(A).call()
    second_expiration = service_registry.functions.service_valid_till(A).call()
    assert second_expiration == first_expiration + DEFAULT_REGISTRATION_DURATION
    # This time, the list of addresses that have ever made deposits should not grow
    assert service_registry.functions.everMadeDepositsLen().call() == old_len + 1


def test_setURL(
    custom_token: Contract, service_registry: Contract, get_accounts: Callable, web3: Web3
) -> None:
    """A ServiceRegistry allows registered service providers to set their URLs"""
    (A,) = get_accounts(1)
    url1 = "http://example.com"
    url2 = "http://raiden.example.com"

    call_and_transact(custom_token.functions.mint(SERVICE_DEPOSIT), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT),
        {"from": A},
    )
    tx = call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": A})
    tx_receipt = web3.eth.get_transaction_receipt(tx)
    contract_manager = ContractManager(contracts_precompiled_path(version=None))
    event_abi = contract_manager.get_event_abi(CONTRACT_SERVICE_REGISTRY, EVENT_REGISTERED_SERVICE)
    event_data = get_event_data(web3.codec, event_abi, tx_receipt["logs"][-1])
    assert event_data["args"]["service"] == A
    assert event_data["args"]["deposit_contract"] != EMPTY_ADDRESS

    call_and_transact(service_registry.functions.setURL(url1), {"from": A})
    assert service_registry.functions.urls(A).call() == url1

    call_and_transact(service_registry.functions.setURL(url2), {"from": A})
    assert service_registry.functions.urls(A).call() == url2


def test_decayed_price(service_registry: Contract) -> None:
    """Test the exponential decayedPrice() function"""
    assert service_registry.functions.decayedPrice(100000, 0).call() == 100000

    # The minimum price is 1000
    assert service_registry.functions.decayedPrice(100, 0).call() == 1000

    # roughly 139 days till the price halves.
    assert service_registry.functions.decayedPrice(100000, 11990300).call() == 50000


def test_changing_duration(
    service_registry: Contract, get_accounts: Callable, custom_token: Contract
) -> None:
    """The controller can change the registration period of ServiceRegistry"""
    new_duration = 90 * SECONDS_PER_DAY
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=new_duration,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    # make sure that the duration has changed.
    assert service_registry.functions.registration_duration().call() == new_duration
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(2 * SERVICE_DEPOSIT), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, 2 * SERVICE_DEPOSIT),
        {"from": A},
    )
    call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": A})
    first_expiration = service_registry.functions.service_valid_till(A).call()
    call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": A})
    second_expiration = service_registry.functions.service_valid_till(A).call()
    assert second_expiration == first_expiration + new_duration


def test_changing_duration_to_huge_value(
    service_registry: Contract, get_accounts: Callable, custom_token: Contract
) -> None:
    """When the duration is huge and the deadline overflows, deposit fails"""
    new_duration = 2 ** 256 - 1
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=new_duration,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    # make sure that the duration has changed.
    assert service_registry.functions.registration_duration().call() == new_duration
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(2 * SERVICE_DEPOSIT), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, 2 * SERVICE_DEPOSIT),
        {"from": A},
    )
    with pytest.raises(TransactionFailed, match="overflow during extending the registration"):
        call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": A})


def test_changing_bump_numerator(service_registry: Contract) -> None:
    """The controller can change the price bump numerator"""
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR + 1,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert service_registry.functions.price_bump_numerator().call() == DEFAULT_BUMP_NUMERATOR + 1


def test_calling_internal_bump_paramter_change(service_registry: Contract) -> None:
    """Calling an internal function setPriceBumpParameters() must fail"""
    with pytest.raises(MismatchedABI):
        call_and_transact(
            service_registry.functions.setPriceBumpParameters(
                DEFAULT_BUMP_NUMERATOR + 1, DEFAULT_BUMP_DENOMINATOR
            ),
            {"from": DEPLOYER_ADDRESS},
        )


def test_too_high_bump_numerator_fail(service_registry: Contract) -> None:
    """changeParameters() fails if the numerator is too big"""
    with pytest.raises(TransactionFailed, match="price dump numerator is too big"):
        call_and_transact(
            service_registry.functions.changeParameters(
                _price_bump_numerator=2 ** 40,
                _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
                _decay_constant=DEFAULT_DECAY_CONSTANT,
                _min_price=DEFAULT_MIN_PRICE,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": DEPLOYER_ADDRESS},
        )


def test_changing_bump_denominator(service_registry: Contract) -> None:
    """The controller can change the price dump denominator"""
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR + 1,
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert (
        service_registry.functions.price_bump_denominator().call() == DEFAULT_BUMP_DENOMINATOR + 1
    )


def test_changing_too_low_bump_parameter_fail(service_registry: Contract) -> None:
    """changeParameters() fails if the bump numerator is smaller than the bump denominator"""
    with pytest.raises(TransactionFailed, match="price dump instead of bump"):
        call_and_transact(
            service_registry.functions.changeParameters(
                _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
                _price_bump_denominator=DEFAULT_BUMP_NUMERATOR + 1,
                _decay_constant=DEFAULT_DECAY_CONSTANT,
                _min_price=DEFAULT_MIN_PRICE,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": DEPLOYER_ADDRESS},
        )


def test_zero_numerator_fail(service_registry: Contract) -> None:
    """changeParameters() fails if the bump numerator is set to zero"""
    with pytest.raises(TransactionFailed, match="price dump instead of bump"):
        call_and_transact(
            service_registry.functions.changeParameters(
                _price_bump_numerator=0,
                _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
                _decay_constant=DEFAULT_DECAY_CONSTANT,
                _min_price=DEFAULT_MIN_PRICE,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": DEPLOYER_ADDRESS},
        )


def test_changing_decay_constant(service_registry: Contract) -> None:
    """The controller can change the price decay constant"""
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=DEFAULT_DECAY_CONSTANT + 100,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert service_registry.functions.decay_constant().call() == DEFAULT_DECAY_CONSTANT + 100


def test_very_small_decay_cosntant(service_registry: Contract) -> None:
    """set a very small decay constant and see very fast price decay"""
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=1,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert service_registry.functions.decayedPrice(100000, 100).call() == DEFAULT_MIN_PRICE


def test_internal_set_decay_constant(service_registry: Contract) -> None:
    """Calling the internal setDecayConstant() must fail"""
    with pytest.raises(MismatchedABI):
        call_and_transact(
            service_registry.functions.setDecayConstant(DEFAULT_DECAY_CONSTANT + 100),
            {"from": DEPLOYER_ADDRESS},
        )


def test_too_high_decay_constant_fail(service_registry: Contract) -> None:
    """changeParameters() fails if the new decay constant is too high"""
    with pytest.raises(TransactionFailed, match="too big decay constant"):
        call_and_transact(
            service_registry.functions.changeParameters(
                _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
                _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
                _decay_constant=2 ** 40,
                _min_price=DEFAULT_MIN_PRICE,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": DEPLOYER_ADDRESS},
        )


def test_very_big_decay_cosntant(service_registry: Contract) -> None:
    """set a very big decay constant and see very slow price decay"""
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=2 ** 40 - 1,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert service_registry.functions.decayedPrice(100000, 11990300).call() == 99998


def test_zero_denominator_fail(service_registry: Contract) -> None:
    """changeParameters() fails if the new bump denominator is zero"""
    with pytest.raises(TransactionFailed, match="divide by zero"):
        call_and_transact(
            service_registry.functions.changeParameters(
                _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
                _price_bump_denominator=0,
                _decay_constant=DEFAULT_DECAY_CONSTANT,
                _min_price=DEFAULT_MIN_PRICE,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": DEPLOYER_ADDRESS},
        )


def test_changing_min_price(service_registry: Contract) -> None:
    """The controller can change the min_price"""
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=DEFAULT_MIN_PRICE * 2,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert service_registry.functions.min_price().call() == DEFAULT_MIN_PRICE * 2


def test_changing_min_price_above_current(service_registry: Contract) -> None:
    """Changing min_price above the current price."""
    current_price = service_registry.functions.currentPrice().call()
    call_and_transact(
        service_registry.functions.changeParameters(
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=current_price + 1,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        ),
        {"from": DEPLOYER_ADDRESS},
    )
    assert service_registry.functions.currentPrice().call() == current_price + 1


def test_internal_min_price(service_registry: Contract) -> None:
    """Calling the internal setMinPrice() must fail"""
    with pytest.raises(MismatchedABI):
        call_and_transact(
            service_registry.functions.setMinPrice(DEFAULT_MIN_PRICE * 2),
            {"from": DEPLOYER_ADDRESS},
        )


def test_unauthorized_parameter_change(service_registry: Contract, get_accounts: Callable) -> None:
    """A random address's changeParameters() call should fail"""
    (A,) = get_accounts(1)
    with pytest.raises(TransactionFailed, match="Can only be called by controller"):
        call_and_transact(
            service_registry.functions.changeParameters(
                _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
                _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
                _decay_constant=DEFAULT_DECAY_CONSTANT,
                _min_price=DEFAULT_MIN_PRICE * 2,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": A},
        )
    assert service_registry.functions.min_price().call() == DEFAULT_MIN_PRICE


def test_parameter_change_on_no_controller(service_registry_without_controller: Contract) -> None:
    """A random address's changeParameters() call should fail"""
    with pytest.raises(TransactionFailed, match="Can only be called by controller"):
        call_and_transact(
            service_registry_without_controller.functions.changeParameters(
                _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
                _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
                _decay_constant=DEFAULT_DECAY_CONSTANT,
                _min_price=DEFAULT_MIN_PRICE * 2,
                _registration_duration=DEFAULT_REGISTRATION_DURATION,
            ),
            {"from": DEPLOYER_ADDRESS},
        )
    assert service_registry_without_controller.functions.min_price().call() == DEFAULT_MIN_PRICE


def service_registry_with_zero_supply_token(
    deploy_tester_contract: Callable, zero_supply_custom_token: Contract
) -> None:
    """Deployment of ServiceRegistry should fail with a token with zero supply"""
    with pytest.raises(TransactionFailed, match="total supply zero"):
        deploy_tester_contract(
            CONTRACT_SERVICE_REGISTRY,
            [
                zero_supply_custom_token.address,
                EMPTY_ADDRESS,
                2 ** 90,
                2 ** 40 - 1,
                1,
                2 ** 40 - 1,
                DEFAULT_MIN_PRICE,
                DEFAULT_REGISTRATION_DURATION,
            ],
        )


# FIXME: can be removed?
def service_registry_with_high_numbers(
    deploy_tester_contract: Callable, custom_token: Contract
) -> None:
    """See if the computation overflows with the highest allowed numbers"""
    contract = deploy_tester_contract(
        CONTRACT_SERVICE_REGISTRY,
        [
            custom_token.address,
            EMPTY_ADDRESS,
            2 ** 90,
            2 ** 40 - 1,
            1,
            2 ** 40 - 1,
            DEFAULT_MIN_PRICE,
            DEFAULT_REGISTRATION_DURATION,
        ],
    )
    assert contract.functions.currentPrice() == 2 ** 90


def test_deprecation_switch(
    service_registry: Contract, get_accounts: Callable, custom_token: Contract
) -> None:
    """The controller turns on the deprecation switch and somebody tries to deposit"""
    # The controller turns on the deprecation switch
    assert not service_registry.functions.deprecated().call()
    call_and_transact(
        service_registry.functions.setDeprecationSwitch(), {"from": DEPLOYER_ADDRESS}
    )
    assert service_registry.functions.deprecated().call()
    # A user tries to make a deposit
    (A,) = get_accounts(1)
    minted_amount = service_registry.functions.currentPrice().call()
    call_and_transact(custom_token.functions.mint(minted_amount), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, minted_amount),
        {"from": A},
    )
    with pytest.raises(TransactionFailed, match="this contract was deprecated"):
        call_and_transact(service_registry.functions.deposit(minted_amount), {"from": A})


def test_deprecation_immediate_payout(
    create_account: Callable, custom_token: Contract, service_registry: Contract, web3: Web3
) -> None:
    """When the deprecation switch is on, deposits can be withdrawn immediately."""
    # A user makes a deposit
    A = create_account()
    minted = service_registry.functions.currentPrice().call()
    call_and_transact(custom_token.functions.mint(minted), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, minted), {"from": A}
    )
    deposit_tx = call_and_transact(service_registry.functions.deposit(minted), {"from": A})
    # The user obtains the deposit address
    deposit_tx_receipt = web3.eth.get_transaction_receipt(deposit_tx)
    contract_manager = ContractManager(contracts_precompiled_path(version=None))
    event_abi = contract_manager.get_event_abi(CONTRACT_SERVICE_REGISTRY, EVENT_REGISTERED_SERVICE)
    event_data = get_event_data(web3.codec, event_abi, deposit_tx_receipt["logs"][-1])
    deposit_address = event_data["args"]["deposit_contract"]
    # And obtains the Deposit contract instance
    deposit_abi = contract_manager.get_contract_abi(CONTRACT_DEPOSIT)
    deposit = web3.eth.contract(abi=deposit_abi, address=deposit_address)
    # The controller turns on the deprecation switch
    call_and_transact(
        service_registry.functions.setDeprecationSwitch(), {"from": DEPLOYER_ADDRESS}
    )
    # The user successfully withdraws the deposit
    call_and_transact(deposit.functions.withdraw(A), {"from": A})
    # The user has all the balance it has minted
    assert minted == custom_token.functions.balanceOf(A).call()
    # The Deposit contract has destroyed itself
    assert web3.eth.get_code(deposit.address) == HexBytes("0x")


def test_unauthorized_deprecation_switch(
    service_registry: Contract, get_accounts: Callable
) -> None:
    """A random account cannot turn on the deprecation switch"""
    (A,) = get_accounts(1)
    with pytest.raises(TransactionFailed, match="Can only be called by controller"):
        call_and_transact(service_registry.functions.setDeprecationSwitch(), {"from": A})


def test_deploying_service_registry_with_denominator_zero(
    deploy_tester_contract: Callable, custom_token: Contract
) -> None:
    """ServiceRegistry's constructor must fail when denominator is zero"""
    # Web3 does not expose the error message "divide by zero"
    # when require() fails in the constructor.
    with pytest.raises(TransactionFailed, match="divide by zero"):
        deploy_tester_contract(
            CONTRACT_SERVICE_REGISTRY,
            _token_for_registration=custom_token.address,
            _controller=DEPLOYER_ADDRESS,
            _initial_price=int(3000e18),
            _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
            _price_bump_denominator=0,  # instead of DEFAULT_BUMP_DENOMINATOR
            _decay_constant=DEFAULT_DECAY_CONSTANT,
            _min_price=DEFAULT_MIN_PRICE,
            _registration_duration=DEFAULT_REGISTRATION_DURATION,
        )
