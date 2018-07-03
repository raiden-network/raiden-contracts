import pytest
from copy import deepcopy
from random import randint
from raiden_contracts.constants import (
    EVENT_CHANNEL_SETTLED,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.utils.events import check_channel_settled
from raiden_contracts.tests.fixtures.channel_test_values import channel_settle_test_values
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.fixtures.config import fake_hex, fake_bytes
from raiden_contracts.tests.utils import (
    MAX_UINT256,
    get_settlement_amounts,
    get_onchain_settlement_amounts,
    ChannelValues,
)


def test_max_safe_uint256(token_network, token_network_test):
    max_safe_uint256 = token_network_test.functions.get_max_safe_uint256().call()

    assert token_network.functions.MAX_SAFE_UINT256().call() == max_safe_uint256
    assert max_safe_uint256 == MAX_UINT256


def test_settle_no_bp_success(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 6
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    locksroot = fake_bytes(32)
    additional_hash = fake_bytes(32)
    create_channel_and_deposit(A, B, deposit_A, deposit_B)

    # Close channel with no balance proof
    token_network.functions.closeChannel(
        B,
        locksroot,
        0,
        additional_hash,
        fake_bytes(64),
    ).transact({'from': A})

    # Do not call updateNonClosingBalanceProof

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    # Settling the channel should work with no balance proofs
    token_network.functions.settleChannel(
        A,
        0,
        0,
        locksroot,
        B,
        0,
        0,
        locksroot,
    ).transact({'from': A})


@pytest.mark.parametrize('channel_test_values', channel_settle_test_values)
def test_settle_channel_state(
        web3,
        get_accounts,
        custom_token,
        token_network,
        create_channel_and_deposit,
        withdraw_channel,
        close_and_update_channel,
        settle_state_tests,
        channel_test_values,
):
    number_of_channels = 5
    accounts = get_accounts(2 * number_of_channels)
    (vals_A0, vals_B0) = channel_test_values

    # We mimic old balance proofs here, with a high locked amount and lower transferred amount
    # We expect to have the same settlement values as the original values

    def equivalent_transfers(balance_proof):
        new_balance_proof = deepcopy(balance_proof)
        new_balance_proof.locked = randint(
            balance_proof.locked,
            balance_proof.transferred + balance_proof.locked,
        )
        new_balance_proof.transferred = (
            balance_proof.transferred +
            balance_proof.locked -
            new_balance_proof.locked
        )
        return new_balance_proof

    vals_A_reversed = deepcopy(vals_A0)
    vals_A_reversed.locked = vals_A0.transferred
    vals_A_reversed.transferred = vals_A0.locked

    vals_B_reversed = deepcopy(vals_B0)
    vals_B_reversed.locked = vals_B0.transferred
    vals_B_reversed.transferred = vals_B0.locked

    new_values = [
        (vals_A0, vals_B0),
        (vals_A_reversed, vals_B_reversed),
    ] + [
        sorted(
            [
                equivalent_transfers(vals_A0),
                equivalent_transfers(vals_B0),
            ],
            key=lambda x: x.transferred + x.locked,
            reverse=False,
        ) for no in range(0, number_of_channels - 1)
    ]

    # Calculate how much A and B should receive
    settlement = get_settlement_amounts(vals_A0, vals_B0)
    # Calculate how much A and B receive according to onchain computation
    settlement2 = get_onchain_settlement_amounts(vals_A0, vals_B0)

    for no in range(0, number_of_channels + 1):
        A = accounts[no]
        B = accounts[no + 1]
        (vals_A, vals_B) = new_values[no]
        vals_A.locksroot = fake_bytes(32, '02')
        vals_B.locksroot = fake_bytes(32, '03')

        create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

        withdraw_channel(A, vals_A.withdrawn, B)
        withdraw_channel(B, vals_B.withdrawn, A)

        close_and_update_channel(
            A,
            vals_A,
            B,
            vals_B,
        )

        web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)

        pre_balance_A = custom_token.functions.balanceOf(A).call()
        pre_balance_B = custom_token.functions.balanceOf(B).call()
        pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

        call_settle(token_network, A, vals_A, B, vals_B)

        # We do the balance & state tests here for each channel and also compare with
        # the expected settlement amounts
        settle_state_tests(
            A,
            vals_A,
            B,
            vals_B,
            pre_balance_A,
            pre_balance_B,
            pre_balance_contract,
        )

        # We compute again the settlement amounts here to compare with the other channel
        # settlement test values, which should be equal

        # Calculate how much A and B should receive
        settlement_equivalent = get_settlement_amounts(vals_A, vals_B)
        assert (
            settlement.participant1_balance +
            settlement.participant2_locked == settlement_equivalent.participant1_balance +
            settlement_equivalent.participant2_locked
        )
        assert (
            settlement.participant2_balance +
            settlement.participant1_locked == settlement_equivalent.participant2_balance +
            settlement_equivalent.participant1_locked
        )

        # Calculate how much A and B receive according to onchain computation
        settlement2_equivalent = get_onchain_settlement_amounts(vals_A, vals_B)
        assert (
            settlement2.participant1_balance +
            settlement2.participant2_locked == settlement2_equivalent.participant1_balance +
            settlement2_equivalent.participant2_locked
        )
        assert (
            settlement2.participant2_balance +
            settlement2.participant1_locked == settlement2_equivalent.participant2_balance +
            settlement2_equivalent.participant1_locked
        )


def test_settle_single_direct_transfer_for_closing_party(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
):
    """ Test settle of a channel with one direct transfer to the participant
    that called close.
    """
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=1, withdrawn=0, transferred=0, locked=0),
        ChannelValues(deposit=10, withdrawn=0, transferred=5, locked=0),
    )
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    locksroot = fake_bytes(32)

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, vals_A.deposit, B)
    channel_deposit(B, vals_B.deposit, A)

    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked,
        1,
        locksroot,
    )
    token_network.functions.closeChannel(B, *balance_proof_B).transact({'from': A})

    web3.testing.mine(settle_timeout)
    token_network.functions.settleChannel(
        A,
        0,
        0,
        locksroot,
        B,
        vals_B.transferred,
        0,
        locksroot,
    ).transact({'from': A})

    # Calculate how much A and B should receive
    expected_settlement = get_settlement_amounts(vals_A, vals_B)
    # Calculate how much A and B receive according to onchain computation
    onchain_settlement = get_onchain_settlement_amounts(vals_A, vals_B)

    assert (expected_settlement.participant1_balance == onchain_settlement.participant1_balance)
    assert (expected_settlement.participant2_balance == onchain_settlement.participant2_balance)


def test_settle_single_direct_transfer_for_counterparty(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ Test settle of a channel with one direct transfer to the participant
    that did not call close.
    """
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=10, withdrawn=0, transferred=5, locked=0),
        ChannelValues(deposit=1, withdrawn=0, transferred=0, locked=0),
    )
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    locksroot = fake_bytes(32)
    additional_hash = fake_bytes(32)

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, vals_A.deposit, B)
    channel_deposit(B, vals_B.deposit, A)
    token_network.functions.closeChannel(
        B,
        locksroot,
        0,
        additional_hash,
        fake_bytes(64),
    ).transact({'from': A})

    balance_proof_A = create_balance_proof(
        channel_identifier,
        A,
        vals_A.transferred,
        vals_A.locked,
        1,
        locksroot)

    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    token_network.functions.updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).transact({'from': B})

    web3.testing.mine(settle_timeout)
    token_network.functions.settleChannel(
        B,
        0,
        0,
        locksroot,
        A,
        vals_A.transferred,
        0,
        locksroot,
    ).transact({'from': B})

    # Calculate how much A and B should receive
    expected_settlement = get_settlement_amounts(vals_B, vals_A)
    # Calculate how much A and B receive according to onchain computation
    onchain_settlement = get_onchain_settlement_amounts(vals_B, vals_A)

    assert (expected_settlement.participant1_balance == onchain_settlement.participant1_balance)
    assert (expected_settlement.participant2_balance == onchain_settlement.participant2_balance)


def test_settle_channel_event(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
        event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    locksroot = fake_hex(32, '00')

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, deposit_A, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 1, locksroot)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, locksroot)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    token_network.functions.closeChannel(B, *balance_proof_B).transact({'from': A})
    token_network.functions.updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).transact({'from': B})

    web3.testing.mine(settle_timeout)
    txn_hash = token_network.functions.settleChannel(
        B,
        5,
        0,
        locksroot,
        A,
        10,
        0,
        locksroot,
    ).transact({'from': A})

    ev_handler.add(txn_hash, EVENT_CHANNEL_SETTLED, check_channel_settled(
        channel_identifier,
        5,
        5,
    ))
    ev_handler.check()
