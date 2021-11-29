from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing.evm import HexAddress
from web3.contract import Contract

from raiden_contracts.constants import (
    MAX_ETH_CHANNEL_PARTICIPANT,
    MAX_ETH_TOKEN_NETWORK,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
    ParticipantInfoIndex,
)
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS, UINT256_MAX


def test_register_three_but_not_four(
    get_token_network_registry: Callable,
    secret_registry_contract: Contract,
    custom_token_factory: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """Check that TokenNetworkRegistry observes the max number of tokens"""
    token_network_registry = get_token_network_registry(
        _secret_registry_address=secret_registry_contract.address,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
        _max_token_networks=3,
    )
    assert token_network_registry.functions.max_token_networks().call() == 3
    token0 = custom_token_factory()
    token1 = custom_token_factory()
    token2 = custom_token_factory()
    token3 = custom_token_factory()
    token4 = custom_token_factory()
    call_and_transact(
        token_network_registry.functions.createERC20TokenNetwork(
            token0.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )
    )
    # Registering the same token again must fail
    with pytest.raises(TransactionFailed, match="TNR: token already registered"):
        call_and_transact(
            token_network_registry.functions.createERC20TokenNetwork(
                token0.address,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            )
        )
    call_and_transact(
        token_network_registry.functions.createERC20TokenNetwork(
            token1.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )
    )
    call_and_transact(
        token_network_registry.functions.createERC20TokenNetwork(
            token2.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )
    )
    with pytest.raises(TransactionFailed, match="TNR: registry full"):
        token_network_registry.functions.createERC20TokenNetwork(
            token3.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call()

    # Now remove the limit and try again
    call_and_transact(token_network_registry.functions.removeLimits(), {"from": DEPLOYER_ADDRESS})
    with pytest.raises(TransactionFailed, match="TNR: limits must be set to MAX_INT"):
        call_and_transact(
            token_network_registry.functions.createERC20TokenNetwork(
                token4.address,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            )
        )
    call_and_transact(
        token_network_registry.functions.createERC20TokenNetwork(
            token4.address,
            UINT256_MAX,
            UINT256_MAX,
        )
    )


def test_channel_participant_deposit_limit_value(token_network: Contract) -> None:
    """Check the channel participant deposit limit"""
    limit = token_network.functions.channel_participant_deposit_limit().call()
    assert limit == MAX_ETH_CHANNEL_PARTICIPANT


def test_network_deposit_limit_value(token_network: Contract) -> None:
    """Check the token network deposit limit"""
    limit = token_network.functions.token_network_deposit_limit().call()
    assert limit == MAX_ETH_TOKEN_NETWORK


def test_participant_deposit_limit(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    assign_tokens: Callable,
) -> None:
    """Observe failure to deposit a bit more tokens than the participant deposit limit"""
    (A, B) = get_accounts(2)
    deposit_A = 100000
    deposit_B = 100000
    channel_identifier = create_channel(A, B)[0]
    assign_tokens(A, MAX_ETH_CHANNEL_PARTICIPANT + 10)
    assign_tokens(B, MAX_ETH_CHANNEL_PARTICIPANT + 10)

    with pytest.raises(TransactionFailed, match="TN/deposit: deposit limit reached"):
        token_network.functions.setTotalDeposit(
            channel_identifier, A, MAX_ETH_CHANNEL_PARTICIPANT + 1, B
        ).call({"from": A})
    with pytest.raises(TransactionFailed, match="TN/deposit: deposit limit reached"):
        token_network.functions.setTotalDeposit(
            channel_identifier, B, MAX_ETH_CHANNEL_PARTICIPANT + 1, A
        ).call({"from": B})

    # Deposit some tokens, under the limit
    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, A, deposit_A, B),
        {"from": A},
    )
    info_A = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert info_A[ParticipantInfoIndex.DEPOSIT] == deposit_A

    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, B, deposit_B, A),
        {"from": B},
    )
    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.DEPOSIT] == deposit_B

    with pytest.raises(TransactionFailed, match="TN/deposit: deposit limit reached"):
        token_network.functions.setTotalDeposit(
            channel_identifier, A, MAX_ETH_CHANNEL_PARTICIPANT + 1, B
        ).call({"from": A})
    with pytest.raises(TransactionFailed, match="TN/deposit: deposit limit reached"):
        token_network.functions.setTotalDeposit(
            channel_identifier, B, MAX_ETH_CHANNEL_PARTICIPANT + 1, A
        ).call({"from": B})

    call_and_transact(
        token_network.functions.setTotalDeposit(
            channel_identifier, A, MAX_ETH_CHANNEL_PARTICIPANT, B
        ),
        {"from": A},
    )
    call_and_transact(
        token_network.functions.setTotalDeposit(
            channel_identifier, B, MAX_ETH_CHANNEL_PARTICIPANT, A
        ),
        {"from": B},
    )

    # Now disable the limits and try again
    with pytest.raises(TransactionFailed, match="Can only be called by"):
        call_and_transact(token_network.functions.removeLimits())
    call_and_transact(token_network.functions.removeLimits(), {"from": DEPLOYER_ADDRESS})
    token_network.functions.setTotalDeposit(
        channel_identifier, B, MAX_ETH_CHANNEL_PARTICIPANT + 1, A
    ).call({"from": B})


@pytest.mark.skip(reason="Only for local testing, otherwise it takes too much time to run.")
def test_network_deposit_limit(
    create_account: Callable,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    assign_tokens: Callable,
) -> None:
    last_deposit = 100

    # ! Only for testing, otherwise we need 1300+ channels and test needs a lot of time to complete
    # ! The token_network_deposit_limit also needs to be changed for this to work
    MAX_ETH_TOKEN_NETWORK_TESTING = int(1 * 10 ** 18)

    def remaining() -> int:
        return (
            MAX_ETH_TOKEN_NETWORK_TESTING
            - custom_token.functions.balanceOf(token_network.address).call()
            - last_deposit
        )

    def send_remaining(
        channel_identifier: int, participant1: HexAddress, participant2: HexAddress
    ) -> None:
        remaining_to_reach_limit = remaining()
        assign_tokens(participant1, remaining_to_reach_limit)
        call_and_transact(
            token_network.functions.setTotalDeposit(
                channel_identifier, participant1, remaining_to_reach_limit, participant2
            ),
            {"from": participant1},
        )

    remaining_to_reach_limit = remaining()
    while remaining_to_reach_limit > 0:
        A = create_account()
        B = create_account()
        assign_tokens(A, MAX_ETH_CHANNEL_PARTICIPANT)
        assign_tokens(B, MAX_ETH_CHANNEL_PARTICIPANT)
        channel_identifier = create_channel(A, B)[0]

        try:
            call_and_transact(
                token_network.functions.setTotalDeposit(
                    channel_identifier, A, MAX_ETH_CHANNEL_PARTICIPANT, B
                ),
                {"from": A},
            )
        except TransactionFailed:
            send_remaining(channel_identifier, A, B)
            break

        try:
            call_and_transact(
                token_network.functions.setTotalDeposit(
                    channel_identifier, B, MAX_ETH_CHANNEL_PARTICIPANT, A
                ),
                {"from": B},
            )
        except TransactionFailed:
            send_remaining(channel_identifier, B, A)
            break

        remaining_to_reach_limit = remaining()

    assert (
        MAX_ETH_TOKEN_NETWORK_TESTING
        - custom_token.functions.balanceOf(token_network.address).call()
        == last_deposit
    )

    A = create_account()
    B = create_account()
    assign_tokens(A, last_deposit + 10)
    channel_identifier = create_channel(A, B)[0]

    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, A, last_deposit, B),
        {"from": A},
    )

    # After token network limit is reached, we cannot deposit anymore tokens in existent channels
    with pytest.raises(TransactionFailed, match="abc"):
        token_network.functions.setTotalDeposit(channel_identifier, A, 1, B).call({"from": A})

    # After token network limit is reached, we cannot open new channels
    C = create_account()
    D = create_account()
    with pytest.raises(TransactionFailed, match="abc"):
        create_channel(C, D)

    # Now disable the limits and try again
    call_and_transact(token_network.functions.removeLimits(), {"from": DEPLOYER_ADDRESS})
    token_network.functions.setTotalDeposit(channel_identifier, A, 1, B).call({"from": A})
