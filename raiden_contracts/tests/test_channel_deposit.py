import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelEvent
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_ADDRESS,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    FAKE_ADDRESS,
    MAX_UINT256,
    ChannelValues,
)
from raiden_contracts.utils.events import check_new_deposit


def test_deposit_channel_call(token_network, custom_token, create_channel, get_accounts):
    """ Calling setTotalDeposit() fails with various invalid inputs """
    (A, B) = get_accounts(2)
    deposit_A = 200
    channel_identifier = create_channel(A, B)[0]

    custom_token.functions.mint(deposit_A).call_and_transact({'from': A})

    custom_token.functions.approve(token_network.address, deposit_A).call_and_transact({'from': A})

    # Validation failure with an invalid channel identifier
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            -1,
            A,
            deposit_A,
            B,
        )
    # Validation failure with the empty string instead of a channel identifier
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            '',
            A,
            deposit_A,
            B,
        )
    # Validation failure with a negative number instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            -1,
            A,
            deposit_A,
        )
    # Validation failure with an empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            '',
            deposit_A,
            B,
        )
    # Validation failure with an odd-length string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            FAKE_ADDRESS,
            deposit_A,
            B,
        )
    # Validation failure with the number zero instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            0x0,
            deposit_A,
            B,
        )
    # Validation failure with the empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            deposit_A,
            '',
        )
    # Validation failure with an odd-length string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            deposit_A,
            FAKE_ADDRESS,
        )
    # Validation failure with the number zero instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            deposit_A,
            0x0,
        )
    # Validation failure with a negative amount of deposit
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            -1,
            B,
        )
    # Transaction failure with the zero address
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            EMPTY_ADDRESS,
            deposit_A,
            B,
        ).call({'from': A})
    # Transaction failure with the zero address
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            deposit_A,
            EMPTY_ADDRESS,
        ).call({'from': A})
    # Transaction failure with zero total deposit
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            0,
            B,
        ).call({'from': A})

    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        deposit_A,
        B,
    )


def test_deposit_notapproved(
        token_network,
        custom_token,
        create_channel,
        get_accounts,
        web3,
):
    """ Calling setTotalDeposit() fails without approving transfers on the token contract """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    deposit_A = 1

    custom_token.functions.mint(deposit_A).call_and_transact({'from': A})
    web3.testing.mine(1)
    balance = custom_token.functions.balanceOf(A).call()
    assert balance >= deposit_A, f'minted {deposit_A} but the balance is still {balance}'

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            deposit_A,
            B,
        ).call({'from': A})


def test_null_or_negative_deposit_fail(
        token_network,
        create_channel,
        channel_deposit,
        assign_tokens,
        get_accounts,
):
    """ setTotalDeposit() fails when the total deposit does not increase """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 2, B)

    assign_tokens(A, 1)

    # setTotalDeposit is idempotent
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(channel_identifier, A, 2, B).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(channel_identifier, A, 1, B).call({'from': A})


def test_deposit_delegate_works(token_network, get_accounts, create_channel, channel_deposit):
    """ A third party can successfully call setTokenDeposit() """
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 2, B, tx_from=C)


def test_deposit_wrong_channel(
        get_accounts,
        token_network,
        create_channel,
        assign_tokens,
):
    """ setTotalDeposit() with a wrong channelID fails """
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_identifier2 = create_channel(A, C)[0]
    assign_tokens(A, 10)

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier2,
            A,
            10,
            B,
        ).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            10,
            C,
        ).call({'from': A})

    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        10,
        B,
    ).call_and_transact({'from': A})


@pytest.mark.skip('Not necessary with limited deposits for the test release.')
def test_channel_deposit_overflow(token_network, get_accounts, create_channel, channel_deposit):
    (A, B) = get_accounts(2)
    deposit_A = 50
    deposit_B_ok = MAX_UINT256 - deposit_A
    deposit_B_fail = deposit_B_ok + 1

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    with pytest.raises(TransactionFailed):
        channel_deposit(channel_identifier, B, deposit_B_fail, A)

    channel_deposit(channel_identifier, B, deposit_B_ok, A)


def test_deposit_channel_state(token_network, create_channel, channel_deposit, get_accounts):
    """ Observe how setTotalDeposit() changes the results of getChannelParticipantInfo() """
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    channel_identifier = create_channel(A, B)[0]

    A_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        A,
        B,
    ).call()[0]
    assert A_deposit == 0

    B_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        B,
        A,
    ).call()[0]
    assert B_deposit == 0

    channel_deposit(channel_identifier, A, deposit_A, B)
    A_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        A,
        B,
    ).call()[0]
    assert A_deposit == deposit_A
    B_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        B,
        A,
    ).call()[0]
    assert B_deposit == 0

    channel_deposit(channel_identifier, B, deposit_B, A)
    A_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        A,
        B,
    ).call()[0]
    assert A_deposit == deposit_A
    B_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier,
        B,
        A,
    ).call()[0]
    assert B_deposit == deposit_B


def test_deposit_wrong_state_fail(
        web3,
        get_accounts,
        token_network,
        create_channel,
        assign_tokens,
        close_and_update_channel,
):
    """ setTotalDeposit() fails on Closed or Settled channels. """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(deposit=2, transferred=0, locked=0)
    vals_B = ChannelValues(deposit=2, transferred=0, locked=0)
    channel_identifier = create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)[0]
    assign_tokens(A, vals_A.deposit)
    assign_tokens(B, vals_B.deposit)
    token_network.functions.setTotalDeposit(
        channel_identifier,
        A,
        vals_A.deposit,
        B,
    ).call_and_transact({'from': A})
    token_network.functions.setTotalDeposit(
        channel_identifier,
        B,
        vals_B.deposit,
        A,
    ).call_and_transact({'from': B})

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    assign_tokens(A, 10)
    assign_tokens(B, 10)
    vals_A.deposit += 5
    vals_B.deposit += 5
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            vals_A.deposit,
            B,
        ).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            vals_B.deposit,
            A,
        ).call({'from': B})

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            vals_A.deposit,
            B,
        ).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            vals_B.deposit,
            A,
        ).call({'from': B})


def test_deposit_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        event_handler,
):
    """ setTotalDeposit() from each participant causes a DEPOSIT event """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    channel_identifier = create_channel(A, B)[0]

    txn_hash = channel_deposit(channel_identifier, A, deposit_A, B)

    ev_handler.add(
        txn_hash,
        ChannelEvent.DEPOSIT,
        check_new_deposit(channel_identifier, A, deposit_A),
    )

    txn_hash = channel_deposit(channel_identifier, B, deposit_B, A)
    ev_handler.add(
        txn_hash,
        ChannelEvent.DEPOSIT,
        check_new_deposit(channel_identifier, B, deposit_B),
    )

    ev_handler.check()
