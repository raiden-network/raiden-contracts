from typing import Callable

import pytest
from eth_typing.evm import HexAddress
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_USER_DEPOSIT
from raiden_contracts.tests.fixtures.token import CUSTOM_TOKEN_TOTAL_SUPPLY
from raiden_contracts.tests.utils import call_and_transact


@pytest.fixture(scope="session")
def user_deposit_whole_balance_limit() -> int:
    return CUSTOM_TOKEN_TOTAL_SUPPLY // 100


@pytest.fixture(scope="session")
def uninitialized_user_deposit_contract(
    deploy_tester_contract: Callable,
    custom_token: Contract,
    user_deposit_whole_balance_limit: int,
) -> Contract:
    return deploy_tester_contract(
        CONTRACT_USER_DEPOSIT,
        _token_address=custom_token.address,
        _whole_balance_limit=user_deposit_whole_balance_limit,
    )


@pytest.fixture
def user_deposit_contract(
    uninitialized_user_deposit_contract: Contract,
    monitoring_service_external: Contract,
    one_to_n_contract: Contract,
) -> Contract:
    call_and_transact(
        uninitialized_user_deposit_contract.functions.init(
            monitoring_service_external.address, one_to_n_contract.address
        )
    )
    return uninitialized_user_deposit_contract


@pytest.fixture
def udc_transfer_contract(
    deploy_tester_contract: Callable, uninitialized_user_deposit_contract: Contract
) -> Contract:
    return deploy_tester_contract(
        "UDCTransfer", udc_address=uninitialized_user_deposit_contract.address
    )


@pytest.fixture
def deposit_to_udc(user_deposit_contract: Contract, custom_token: Contract) -> Callable:
    def deposit(receiver: HexAddress, amount: int) -> None:
        """Uses UDC's monotonous deposit amount handling

        If you call it twice, only amount2 - amount1 will be deposited. More
        will be mined and approved to keep the implementation simple, though.
        """
        call_and_transact(custom_token.functions.mint(amount), {"from": receiver})
        call_and_transact(
            custom_token.functions.approve(user_deposit_contract.address, amount),
            {"from": receiver},
        )
        call_and_transact(
            user_deposit_contract.functions.deposit(receiver, amount),
            {"from": receiver},
        )

    return deposit
