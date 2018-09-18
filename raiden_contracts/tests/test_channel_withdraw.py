import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError
from raiden_contracts.utils.events import check_withdraw
from raiden_contracts.constants import (
    ChannelEvent,
    ChannelState,
    TEST_SETTLE_TIMEOUT_MIN,
)
from .utils import MAX_UINT256
from raiden_contracts.tests.fixtures.config import (
    EMPTY_BALANCE_HASH,
    EMPTY_LOCKSROOT,
    EMPTY_ADDITIONAL_HASH,
    EMPTY_SIGNATURE,
    EMPTY_ADDRESS,
)


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_call(
        token_network,
        create_channel_and_deposit,
        get_accounts,
        create_withdraw_signatures,
):
    (A, B) = get_accounts(2)
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, 10, 1)

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A,
    )

    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            0x0,
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            '',
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            -1,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            MAX_UINT256 + 1,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            EMPTY_ADDRESS,
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            0,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            EMPTY_SIGNATURE,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A,
            EMPTY_SIGNATURE,
        ).transact({'from': A})

    token_network.functions.setTotalWithdraw(
        channel_identifier,
        A,
        withdraw_A,
        signature_A_for_A,
        signature_B_for_A,
    ).transact({'from': A})


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_wrong_state(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
):
    (A, B) = get_accounts(2)
    withdraw_A = 1

    assert token_network.functions.getChannelIdentifier(A, B).call() == 0

    channel_identifier = create_channel_and_deposit(A, B, 10, 14, TEST_SETTLE_TIMEOUT_MIN)
    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.OPENED

    # Channel is open, withdraw must work
    withdraw_channel(channel_identifier, A, withdraw_A, B)

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': A})
    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.CLOSED

    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, withdraw_A, B)

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        channel_identifier,
        A,
        0,
        0,
        EMPTY_LOCKSROOT,
        B,
        0,
        0,
        EMPTY_LOCKSROOT,
    ).transact({'from': A})
    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.REMOVED

    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, withdraw_A, B)


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_bigger(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
):
    (A, B) = get_accounts(2)
    deposit_A = 15
    deposit_B = 13

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, deposit_A + deposit_B + 1, B)
    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, B, deposit_A + deposit_B + 1, A)

    withdraw_channel(channel_identifier, A, 3, B)
    withdraw_channel(channel_identifier, B, 6, A)
    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, deposit_A + deposit_B - 5, B)
    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, B, deposit_A + deposit_B - 2, A)

    withdraw_channel(channel_identifier, A, deposit_A + deposit_B - 7, B)


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_wrong_signers(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
        create_withdraw_signatures,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 15
    deposit_B = 13
    withdraw_A = 5
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A_for_A, signature_B_for_A, signature_C_for_A) = create_withdraw_signatures(
        [A, B, C],
        channel_identifier,
        A,
        withdraw_A,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_C_for_A,
            signature_B_for_A,
        ).transact({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A,
            signature_C_for_A,
        ).transact({'from': C})

    token_network.functions.setTotalWithdraw(
        channel_identifier,
        A,
        withdraw_A,
        signature_A_for_A,
        signature_B_for_A,
    ).transact({'from': C})


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_wrong_signature_content(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
        create_withdraw_signatures,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 15
    deposit_B = 13
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    channel_identifier_fake = token_network.functions.getChannelIdentifier(A, C).call()

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A,
    )
    (signature_A_for_A_fake1, signature_B_for_A_fake1) = create_withdraw_signatures(
        [A, B],
        channel_identifier_fake,
        A,
        withdraw_A,
    )
    (signature_A_for_A_fake2, signature_B_for_A_fake2) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        B,
        withdraw_A,
    )
    (signature_A_for_A_fake3, signature_B_for_A_fake3) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A - 1,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A_fake1,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A_fake1,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A_fake2,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A_fake2,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A_fake3,
            signature_B_for_A,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A_fake3,
        ).transact({'from': A})

    token_network.functions.setTotalWithdraw(
        channel_identifier,
        A,
        withdraw_A,
        signature_A_for_A,
        signature_B_for_A,
    ).transact({'from': A})


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_channel_state(
        get_accounts,
        token_network,
        custom_token,
        create_channel_and_deposit,
        withdraw_channel,
        withdraw_state_tests,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 15
    withdraw_B = 2

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_C = custom_token.functions.balanceOf(C).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    (_, withdrawn_amount, _, _, _, _, _) = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        A,
        B,
    ).call()
    assert withdrawn_amount == 0

    withdraw_channel(channel_identifier, A, withdraw_A, B, C)

    withdraw_state_tests(
        channel_identifier,
        A,
        deposit_A,
        withdraw_A,
        0,
        balance_A,
        B,
        deposit_B,
        0,
        balance_B,
        balance_contract,
        C, balance_C,
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_C = custom_token.functions.balanceOf(C).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    withdraw_channel(channel_identifier, B, withdraw_B, A)

    withdraw_state_tests(
        channel_identifier,
        B,
        deposit_B,
        withdraw_B,
        0,
        balance_B,
        A,
        deposit_A,
        withdraw_A,
        balance_A,
        balance_contract,
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_C = custom_token.functions.balanceOf(C).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    withdraw_channel(channel_identifier, B, withdraw_B + 3, A)

    withdraw_state_tests(
        channel_identifier,
        B,
        deposit_B,
        withdraw_B + 3,
        withdraw_B,
        balance_B,
        A,
        deposit_A,
        withdraw_A,
        balance_A,
        balance_contract,
    )


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_replay_reopened_channel(
        web3,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_withdraw_signatures,
):
    (A, B) = get_accounts(2)
    deposit_A = 20
    withdraw_A = 5

    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, A, deposit_A, B)
    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B],
        channel_identifier1,
        A,
        withdraw_A,
    )
    token_network.functions.setTotalWithdraw(
        channel_identifier1,
        A,
        withdraw_A,
        signature_A_for_A,
        signature_B_for_A,
    ).transact({'from': A})

    token_network.functions.closeChannel(
        channel_identifier1,
        A,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': B})
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        channel_identifier1,
        A,
        0,
        0,
        EMPTY_LOCKSROOT,
        B,
        0,
        0,
        EMPTY_LOCKSROOT,
    ).transact({'from': A})

    # Reopen the channel and make sure we cannot use the old withdraw proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, A, deposit_A, B)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier2,
            A,
            withdraw_A,
            signature_A_for_A,
            signature_B_for_A,
        ).transact({'from': A})

    # Signed message with correct channel_identifier must work
    (signature_A_for_A2, signature_B_for_A2) = create_withdraw_signatures(
        [A, B],
        channel_identifier2,
        A,
        withdraw_A,
    )
    token_network.functions.setTotalWithdraw(
        channel_identifier2,
        A,
        withdraw_A,
        signature_A_for_A2,
        signature_B_for_A2,
    ).transact({'from': A})


@pytest.mark.skip(reason='Delayed until another milestone')
def test_withdraw_event(
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
        event_handler,
):
    (A, B, C) = get_accounts(3)
    ev_handler = event_handler(token_network)

    channel_identifier = create_channel_and_deposit(A, B, 10, 1)

    txn_hash = withdraw_channel(channel_identifier, A, 5, B)
    ev_handler.add(txn_hash, ChannelEvent.WITHDRAW, check_withdraw(channel_identifier, A, 5))

    txn_hash = withdraw_channel(channel_identifier, B, 2, A, C)
    ev_handler.add(txn_hash, ChannelEvent.WITHDRAW, check_withdraw(channel_identifier, B, 2))

    ev_handler.check()
