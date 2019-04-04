import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import (
    MAX_ETH_CHANNEL_PARTICIPANT,
    MAX_ETH_TOKEN_NETWORK,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
    ParticipantInfoIndex,
)


def test_register_three_but_not_four(
        web3,
        get_token_network_registry,
        secret_registry_contract,
        custom_token_factory,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ Check that TokenNetworkRegistry observes the max number of tokens """
    token_network_registry = get_token_network_registry([
        secret_registry_contract.address,
        int(web3.version.network),
        TEST_SETTLE_TIMEOUT_MIN,
        TEST_SETTLE_TIMEOUT_MAX,
        3,
    ])
    assert token_network_registry.functions.max_token_networks().call() == 3
    token0 = custom_token_factory()
    token1 = custom_token_factory()
    token2 = custom_token_factory()
    token3 = custom_token_factory()
    token_network_registry.functions.createERC20TokenNetwork(
        token0.address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ).call_and_transact()
    token_network_registry.functions.createERC20TokenNetwork(
        token1.address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ).call_and_transact()
    token_network_registry.functions.createERC20TokenNetwork(
        token2.address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ).call_and_transact()
    with pytest.raises(TransactionFailed):
        token_network_registry.functions.createERC20TokenNetwork(
            token3.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call()


def test_channel_participant_deposit_limit_value(token_network):
    """ Check the channel participant deposit limit """
    limit = token_network.functions.channel_participant_deposit_limit().call()
    assert limit == MAX_ETH_CHANNEL_PARTICIPANT


def test_network_deposit_limit_value(token_network):
    """ Check the token network deposit limit """
    limit = token_network.functions.token_network_deposit_limit().call()
    assert limit == MAX_ETH_TOKEN_NETWORK


def test_participant_deposit_limit(
        get_accounts,
        token_network,
        create_channel,
        assign_tokens,
):
    """ Observe failure to deposit a bit more tokens than the participant deposit limit """
    (A, B) = get_accounts(2)
    deposit_A = 100000
    deposit_B = 100000
    channel_identifier = create_channel(A, B)[0]
    assign_tokens(A, MAX_ETH_CHANNEL_PARTICIPANT + 10)
    assign_tokens(B, MAX_ETH_CHANNEL_PARTICIPANT + 10)

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            B,
        ).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            A,
        ).call({'from': B})

    # Deposit some tokens, under the limit
    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        deposit_A,
        B,
    ).call_and_transact({'from': A})
    info_A = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert info_A[ParticipantInfoIndex.DEPOSIT] == deposit_A

    info_B = token_network.functions.setTotalDeposit(
        channel_identifier,
        B,
        deposit_B,
        A,
    ).call_and_transact({'from': B})
    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.DEPOSIT] == deposit_B

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            B,
        ).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            A,
        ).call({'from': B})

    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        MAX_ETH_CHANNEL_PARTICIPANT,
        B,
    ).call_and_transact({'from': A})
    token_network.functions.setTotalDeposit(
        channel_identifier,
        B,
        MAX_ETH_CHANNEL_PARTICIPANT,
        A,
    ).call_and_transact({'from': B})


@pytest.mark.skip(reason='Only for local testing, otherwise it takes too much time to run.')
def test_network_deposit_limit(
        web3,
        create_account,
        custom_token,
        token_network,
        create_channel,
        assign_tokens,
):
    last_deposit = 100

    # ! Only for testing, otherwise we need 1300+ channels and test needs a lot of time to complete
    # ! The token_network_deposit_limit also needs to be changed for this to work
    MAX_ETH_TOKEN_NETWORK_TESTING = int(1 * 10**18)

    def remaining():
        return MAX_ETH_TOKEN_NETWORK_TESTING - custom_token.functions.balanceOf(
            token_network.address,
        ).call() - last_deposit

    def send_remaining(channel_identifier, participant1, participant2):
        remaining_to_reach_limit = remaining()
        assign_tokens(participant1, remaining_to_reach_limit)
        token_network.functions.setTotalDeposit(
            channel_identifier,
            participant1,
            remaining_to_reach_limit,
            participant2,
        ).call_and_transact({'from': participant1})

    remaining_to_reach_limit = remaining()
    while remaining_to_reach_limit > 0:
        A = create_account()
        B = create_account()
        assign_tokens(A, MAX_ETH_CHANNEL_PARTICIPANT)
        assign_tokens(B, MAX_ETH_CHANNEL_PARTICIPANT)
        channel_identifier = create_channel(A, B)[0]

        try:
            token_network.functions.setTotalDeposit(
                channel_identifier,
                A,
                MAX_ETH_CHANNEL_PARTICIPANT,
                B,
            ).call_and_transact({'from': A})
        except TransactionFailed:
            send_remaining(channel_identifier, A, B)
            break

        try:
            token_network.functions.setTotalDeposit(
                channel_identifier,
                B,
                MAX_ETH_CHANNEL_PARTICIPANT,
                A,
            ).call_and_transact({'from': B})
        except TransactionFailed:
            send_remaining(channel_identifier, B, A)
            break

        remaining_to_reach_limit = remaining()

    assert MAX_ETH_TOKEN_NETWORK_TESTING - custom_token.functions.balanceOf(
        token_network.address,
    ).call() == last_deposit

    A = create_account()
    B = create_account()
    assign_tokens(A, last_deposit + 10)
    channel_identifier = create_channel(A, B)[0]

    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        last_deposit,
        B,
    ).call_and_transact({'from': A})

    # After token network limit is reached, we cannot deposit anymore tokens in existent channels
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            1,
            B,
        ).call({'from': A})

    # After token network limit is reached, we cannot open new channels
    C = create_account()
    D = create_account()
    with pytest.raises(TransactionFailed):
        create_channel(C, D)
