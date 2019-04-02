from collections import namedtuple

import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelEvent, ChannelState
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_ADDRESS,
    EMPTY_BALANCE_HASH,
    EMPTY_LOCKSROOT,
    EMPTY_SIGNATURE,
    ChannelValues,
    fake_bytes,
)
from raiden_contracts.utils.events import check_transfer_updated


def test_update_call(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ Call updateNonClosingBalanceProof() with various wrong arguments """
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 15, B)
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    (balance_hash, nonce, additional_hash, closing_signature) = balance_proof_A

    # Failure with the zero address instead of A's address
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            EMPTY_ADDRESS,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': C})

    # Failure with the zero address instead of B's address
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            EMPTY_ADDRESS,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': C})

    # Failure with the zero signature
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            EMPTY_SIGNATURE,
        ).call({'from': C})

    # Failure with the empty balance hash
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            EMPTY_BALANCE_HASH,
            nonce,
            additional_hash,
            closing_signature,
            balance_proof_update_signature_B,
        ).call({'from': C})

    # Failure with nonce zero
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_hash,
            0,
            additional_hash,
            closing_signature,
            balance_proof_update_signature_B,
        ).call({'from': C})

    # Failure with the empty signature
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_hash,
            nonce,
            additional_hash,
            EMPTY_SIGNATURE,
            balance_proof_update_signature_B,
        ).call({'from': C})

    # See a success to make sure the above failures are not spurious
    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        balance_hash,
        nonce,
        additional_hash,
        closing_signature,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': C})


def test_update_nonexistent_fail(
        get_accounts,
        token_network,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ updateNonClosingBalanceProof() on a not-yet openned channel should fail """
    (A, B, C) = get_accounts(3)
    channel_identifier = 1

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert settle_block_number == 0
    assert state == ChannelState.NONEXISTENT

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': C})


def test_update_notclosed_fail(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ updateNonClosingBalanceProof() on an Opened channel should fail """
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 25, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert settle_block_number > 0
    assert state == ChannelState.OPENED

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': C})


def test_update_wrong_nonce_fail(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
        update_state_tests,
):
    (A, B, Delegate) = get_accounts(3)
    settle_timeout = 6
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    txn_hash1 = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': Delegate})

    # updateNonClosingBalanceProof should fail for the same nonce as provided previously
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': Delegate})
    balance_proof_A_same_nonce = create_balance_proof(
        channel_identifier,
        A,
        12,
        2,
        balance_proof_A[1],
        fake_bytes(32, '03'),
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_same_nonce,
            balance_proof_update_signature_B,
        ).call({'from': Delegate})

    balance_proof_A_lower_nonce = create_balance_proof(
        channel_identifier,
        A,
        10,
        0,
        4,
        fake_bytes(32, '02'),
    )

    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A_lower_nonce,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_lower_nonce,
            balance_proof_update_signature_B,
        ).call({'from': A})

    update_state_tests(
        channel_identifier,
        A, balance_proof_A,
        B, balance_proof_B,
        settle_timeout,
        txn_hash1,
    )


def test_update_wrong_signatures(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ updateNonClosingBalanceProof() should fail with wrong signatures """
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 25, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_A_fake = create_balance_proof(
        channel_identifier,
        A,
        10,
        0,
        5,
        fake_bytes(32, '02'),
        signer=C,
    )

    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    balance_proof_update_signature_B_fake = create_balance_proof_update_signature(
        C,
        channel_identifier,
        *balance_proof_A,
    )

    # Close the channel so updateNonClosingBalanceProof() is possible
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_fake,
            balance_proof_update_signature_B,
        ).call({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B_fake,
        ).call({'from': C})

    # See a success to make sure that the above failures are not spurious
    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': C})


def test_update_channel_state(
        web3,
        custom_token,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
        update_state_tests,
        txn_cost,
):
    """ A successful updateNonClosingBalanceProof() call should not change token/ETH balances """
    (A, B, Delegate) = get_accounts(3)
    settle_timeout = 6
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    txn_hash1 = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})

    pre_eth_balance_A = web3.eth.getBalance(A)
    pre_eth_balance_B = web3.eth.getBalance(B)
    pre_eth_balance_delegate = web3.eth.getBalance(Delegate)
    pre_eth_balance_contract = web3.eth.getBalance(token_network.address)
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_delegate = custom_token.functions.balanceOf(Delegate).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': Delegate})

    # Test that no balances have changed.
    # There are no transfers to be made in updateNonClosingBalanceProof.
    assert web3.eth.getBalance(A) == pre_eth_balance_A
    assert web3.eth.getBalance(B) == pre_eth_balance_B
    assert web3.eth.getBalance(Delegate) == pre_eth_balance_delegate - txn_cost(txn_hash)
    assert web3.eth.getBalance(token_network.address) == pre_eth_balance_contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(Delegate).call() == pre_balance_delegate
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    update_state_tests(
        channel_identifier,
        A,
        balance_proof_A,
        B,
        balance_proof_B,
        settle_timeout,
        txn_hash1,
    )


def test_update_channel_fail_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ Calls to updateNonClosingBalanceProof() fail with the zero nonce """
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]
    balance_proof_A = create_balance_proof(channel_identifier, A, 0, 0, 0)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            EMPTY_SIGNATURE,
        ).call({'from': B})

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': B})


def test_update_not_allowed_after_settlement_period(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
        web3,
):
    """ updateNonClosingBalanceProof cannot be called after the settlement period. """
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})
    web3.testing.mine(settle_timeout + 1)
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).call({'from': A})


def test_update_not_allowed_for_the_closing_address(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ Closing address cannot call updateNonClosingBalanceProof. """
    (A, B, M) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    # Some balance proof from B
    balance_proof_B_0 = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, '02'))

    # Later balance proof, higher transferred amount, higher nonce
    balance_proof_B_1 = create_balance_proof(channel_identifier, B, 10, 0, 4, fake_bytes(32, '02'))

    # B's signature on the update message is valid
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_B_1,
    )

    # A closes with the first balance proof
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B_0,
    ).call_and_transact({'from': A})

    # Someone wants to update with later balance proof - not possible
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1,
            balance_proof_update_signature_B,
        ).call({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1,
            balance_proof_update_signature_B,
        ).call({'from': B})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1,
            balance_proof_update_signature_B,
        ).call({'from': M})


def test_update_invalid_balance_proof_arguments(
        token_network,
        token_network_test_utils,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ updateNonClosingBalanceProof() should fail on balance proofs with various wrong params """
    (A, B, C) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    balance_proof = namedtuple(
        'balance_proof',
        ['balance_hash', 'nonce', 'additional_hash', 'signature'],
    )

    #  Create valid balance_proof
    balance_proof_valid = balance_proof(*create_balance_proof(
        channel_identifier,
        A,
        10,
        0,
        2,
        fake_bytes(32, '02'),
    ))

    # And a valid nonclosing_signature
    valid_balance_proof_update_signature = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_valid,
    )

    #  We test invalid balance proof arguments with valid signatures

    #  Create balance_proof for invalid token_network
    balance_proof_invalid_token_network = balance_proof(*create_balance_proof(
        channel_identifier,
        A,
        10,
        0,
        2,
        fake_bytes(32, '02'),
        other_token_network=token_network_test_utils,
    ))

    signature_invalid_token_network = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
        other_token_network=token_network_test_utils,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_token_network,
            signature_invalid_token_network,
        ).call({'from': B})

    #  Create balance_proof for invalid channel participant
    balance_proof_invalid_channel_participant = balance_proof(*create_balance_proof(
        channel_identifier,
        C,
        10,
        0,
        2,
        fake_bytes(32, '02'),
    ))

    signature_invalid_channel_participant = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_channel_participant,
            signature_invalid_channel_participant,
        ).call({'from': B})

    #  Create balance_proof for invalid channel identifier
    balance_proof_invalid_channel_identifier = balance_proof(*create_balance_proof(
        channel_identifier + 1,
        A,
        10,
        0,
        2,
        fake_bytes(32, '02'),
    ))

    signature_invalid_channel_identifier = create_balance_proof_update_signature(
        B,
        channel_identifier + 1,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_channel_identifier,
            signature_invalid_channel_identifier,
        ).call({'from': B})

    signature_invalid_balance_hash = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash[::-1],
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash[::-1],  # invalid balance_hash
            balance_proof_valid.nonce,
            balance_proof_valid.additional_hash,
            balance_proof_valid.signature,
            signature_invalid_balance_hash,
        ).call({'from': B})

    signature_invalid_nonce = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        1,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash,
            1,  # invalid nonce
            balance_proof_valid.additional_hash,
            balance_proof_valid.signature,
            signature_invalid_nonce,
        ).call({'from': B})

    signature_invalid_additional_hash = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash[::-1],
        balance_proof_valid.signature,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash,
            balance_proof_valid.nonce,
            fake_bytes(32, '02'),  # invalid additional_hash
            balance_proof_valid.signature,
            signature_invalid_additional_hash,
        ).call({'from': B})

    signature_invalid_closing_signature = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature[::-1],
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash,
            balance_proof_valid.nonce,
            balance_proof_valid.additional_hash,
            balance_proof_valid.signature,
            signature_invalid_closing_signature[::-1],  # invalid non-closing signature
        ).call({'from': B})

    # Call with same balance_proof and signature on valid arguments still works

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_valid,
        valid_balance_proof_update_signature,
    ).call_and_transact({'from': B})


def test_update_signature_on_invalid_arguments(
        token_network,
        token_network_test_utils,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):

    """ Call updateNonClosingBalanceProof with signature on invalid argument fails """
    (A, B, C) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof = namedtuple(
        'balance_proof',
        ['balance_hash', 'nonce', 'additional_hash', 'signature'],
    )

    # Close channel
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    #  Create valid balance_proof
    balance_proof_valid = balance_proof(*create_balance_proof(
        channel_identifier,
        A,
        10,
        0,
        2,
        fake_bytes(32, '02'),
        fake_bytes(32, '02'),
    ))

    signature_invalid_token_network_address = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_valid,
        other_token_network=token_network_test_utils,  # invalid token_network_address
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_token_network_address,
        ).call({'from': B})

    signature_invalid_participant = create_balance_proof_update_signature(
        C,  # invalid signer
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_participant,
        ).call({'from': B})

    signature_invalid_channel_identifier = create_balance_proof_update_signature(
        B,
        channel_identifier + 1,  # invalid channel_identifier
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_channel_identifier,
        ).call({'from': B})

    signature_invalid_balance_hash = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash[::-1],  # invalid balance_hash
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_balance_hash,
        ).call({'from': B})

    signature_invalid_nonce = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        1,  # invalid nonce
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_nonce,
        ).call({'from': B})

    signature_invalid_additional_hash = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        b'\x00' * 32,  # invalid additional_hash
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_additional_hash,
        ).call({'from': B})

    signature_invalid_closing_signature = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature[::-1],
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_closing_signature,
        ).call({'from': B})

    # Call with same balance_proof and signature on valid arguments works
    balance_proof_update_signature = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_valid,
    )
    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_valid,
        balance_proof_update_signature,
    ).call_and_transact({'from': B})


def test_update_replay_reopened_channel(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ updateNonClosingBalanceProof() should refuse a balance proof with a stale channel id """
    (A, B) = get_accounts(2)
    nonce_B = 5
    values_A = ChannelValues(
        deposit=10,
        transferred=0,
        locked=0,
        locksroot=EMPTY_LOCKSROOT,
    )
    values_B = ChannelValues(
        deposit=20,
        transferred=15,
        locked=0,
        locksroot=EMPTY_LOCKSROOT,
    )

    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, B, values_B.deposit, A)
    balance_proof_B = create_balance_proof(
        channel_identifier1,
        B,
        values_B.transferred,
        values_B.locked,
        nonce_B,
        values_B.locksroot,
    )
    balance_proof_update_signature_A = create_balance_proof_update_signature(
        A,
        channel_identifier1,
        *balance_proof_B,
    )

    token_network.functions.closeChannel(
        channel_identifier1,
        A,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': B})

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier1,
        B,
        A,
        *balance_proof_B,
        balance_proof_update_signature_A,
    ).call_and_transact({'from': A})

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)
    token_network.functions.settleChannel(
        channel_identifier1,
        A,
        values_A.transferred,
        values_A.locked,
        values_A.locksroot,
        B,
        values_B.transferred,
        values_B.locked,
        values_B.locksroot,
    ).call_and_transact({'from': A})

    # Make sure we cannot update balance proofs after settleChannel is called
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier1,
            B,
            A,
            *balance_proof_B,
            balance_proof_update_signature_A,
        ).call({'from': A})

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, B, values_B.deposit, A)
    token_network.functions.closeChannel(
        channel_identifier2,
        A,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': B})

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier2,
            B,
            A,
            *balance_proof_B,
            balance_proof_update_signature_A,
        ).call({'from': A})

    # Correct channel_identifier must work
    balance_proof_B2 = create_balance_proof(
        channel_identifier2,
        B,
        values_B.transferred,
        values_B.locked,
        nonce_B,
        values_B.locksroot,
    )
    balance_proof_update_signature_A2 = create_balance_proof_update_signature(
        A,
        channel_identifier2,
        *balance_proof_B2,
    )

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier2,
        B,
        A,
        *balance_proof_B2,
        balance_proof_update_signature_A2,
    ).call_and_transact({'from': A})


def test_update_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
        event_handler,
):
    """ Successful updateNonClosingBalanceProof() emit BALANCE_PROOF_UPDATED events """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    channel_deposit(channel_identifier, B, deposit_B, A)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3)
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 1)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})
    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': B})

    ev_handler.add(
        txn_hash,
        ChannelEvent.BALANCE_PROOF_UPDATED,
        check_transfer_updated(channel_identifier, A, 1),
    )
    ev_handler.check()

    # Test event for second balance proof update
    balance_proof_A2 = create_balance_proof(channel_identifier, A, 4, 0, 2)
    balance_proof_update_signature_B2 = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A2,
    )
    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A2,
        balance_proof_update_signature_B2,
    ).call_and_transact({'from': B})

    ev_handler.add(
        txn_hash,
        ChannelEvent.BALANCE_PROOF_UPDATED,
        check_transfer_updated(channel_identifier, A, 2),
    )
    ev_handler.check()
