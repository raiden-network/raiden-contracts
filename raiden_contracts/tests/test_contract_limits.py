import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import (
    MAX_ETH_CHANNEL_PARTICIPANT,
    MAX_ETH_TOKEN_NETWORK,
    ParticipantInfoIndex,
)


def test_channel_participant_deposit_limit_value(token_network):
    limit = token_network.functions.channel_participant_deposit_limit().call()
    assert limit == MAX_ETH_CHANNEL_PARTICIPANT


def test_network_deposit_limit_value(token_network):
    limit = token_network.functions.token_network_deposit_limit().call()
    assert limit == MAX_ETH_TOKEN_NETWORK


def test_participant_deposit_limit(
        get_accounts,
        token_network,
        create_channel,
        assign_tokens,
):
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
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            A,
        ).transact({'from': B})

    # Deposit some tokens, under the limit
    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        deposit_A,
        B,
    ).transact({'from': A})
    info_A = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert info_A[ParticipantInfoIndex.DEPOSIT] == deposit_A

    info_B = token_network.functions.setTotalDeposit(
        channel_identifier,
        B,
        deposit_B,
        A,
    ).transact({'from': B})
    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.DEPOSIT] == deposit_B

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            B,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            MAX_ETH_CHANNEL_PARTICIPANT + 1,
            A,
        ).transact({'from': B})

    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        MAX_ETH_CHANNEL_PARTICIPANT,
        B,
    ).transact({'from': A})
    token_network.functions.setTotalDeposit(
        channel_identifier,
        B,
        MAX_ETH_CHANNEL_PARTICIPANT,
        A,
    ).transact({'from': B})
