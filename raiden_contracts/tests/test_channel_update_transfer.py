from collections import namedtuple

import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import (
    ChannelEvent,
    ChannelState,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.utils.events import check_transfer_updated
from .fixtures.config import fake_bytes, EMPTY_ADDRESS
from raiden_contracts.tests.utils import ChannelValues
from raiden_contracts.utils.merkle import EMPTY_MERKLE_ROOT


def test_update_call(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 15, B)
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    (balance_hash, nonce, additional_hash, closing_signature) = balance_proof_A

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            EMPTY_ADDRESS,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).transact({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            EMPTY_ADDRESS,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).transact({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            fake_bytes(64),
        ).transact({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            fake_bytes(32),
            nonce,
            additional_hash,
            closing_signature,
            balance_proof_update_signature_B,
        ).transact({'from': C})
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
        ).transact({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_hash,
            nonce,
            additional_hash,
            fake_bytes(64),
            balance_proof_update_signature_B,
        ).transact({'from': C})


def test_update_nonexistent_fail(
        get_accounts,
        token_network,
        create_balance_proof,
        create_balance_proof_update_signature,
):
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
        ).transact({'from': C})


def test_update_notclosed_fail(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
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
        ).transact({'from': C})


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
    ).transact({'from': A})

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).transact({'from': Delegate})

    balance_proof_A_same_nonce = balance_proof_A
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_same_nonce,
            balance_proof_update_signature_B,
        ).transact({'from': Delegate})

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
        ).transact({'from': A})

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

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_fake,
            balance_proof_update_signature_B,
        ).transact({'from': C})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B_fake,
        ).transact({'from': C})


def test_update_channel_state(
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
    ).transact({'from': A})

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).transact({'from': Delegate})

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
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64),
            fake_bytes(64),
        ).transact({'from': B})

    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).transact({'from': B})


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
    ).transact({'from': A})
    web3.testing.mine(settle_timeout)
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A,
            balance_proof_update_signature_B,
        ).transact({'from': A})


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
    ).transact({'from': A})

    # Someone wants to update with later balance proof - not possible
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1,
            balance_proof_update_signature_B,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1,
            balance_proof_update_signature_B,
        ).transact({'from': B})
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1,
            balance_proof_update_signature_B,
        ).transact({'from': M})


def test_update_invalid_balance_proof_arguments(
        token_network,
        token_network_test,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    (A, B, C) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

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
        other_token_network=token_network_test,
    ))

    signature_invalid_token_network = create_balance_proof_update_signature(
        B,
        channel_identifier,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
        other_token_network=token_network_test,
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_token_network,
            signature_invalid_token_network,
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

    # Call with same balance_proof and signature on valid arguments still works

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_valid,
        valid_balance_proof_update_signature,
    ).transact({'from': B})


def test_update_signature_on_invalid_arguments(
        token_network,
        token_network_test,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):

    """ Call updateNonClosingBalanceProof with signature on invalid argument fails. """
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
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

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
        other_token_network=token_network_test,  # invalid token_network_address
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid,
            signature_invalid_token_network_address,
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
        ).transact({'from': B})

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
    ).transact({'from': B})


def test_update_replay_reopened_channel(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    (A, B) = get_accounts(2)
    nonce_A = 0
    nonce_B = 5
    values_A = ChannelValues(
        deposit=10,
        transferred=0,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=20,
        transferred=15,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
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
        fake_bytes(32),
        nonce_A,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': B})

    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier1,
        B,
        A,
        *balance_proof_B,
        balance_proof_update_signature_A,
    ).transact({'from': A})

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
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
    ).transact({'from': A})

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, B, values_B.deposit, A)
    token_network.functions.closeChannel(
        channel_identifier2,
        A,
        fake_bytes(32),
        nonce_A,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': B})

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier2,
            B,
            A,
            *balance_proof_B,
            balance_proof_update_signature_A,
        ).transact({'from': A})

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
    ).transact({'from': A})


def test_update_channel_event(
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
    ).transact({'from': A})
    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).transact({'from': B})

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
    ).transact({'from': B})

    ev_handler.add(
        txn_hash,
        ChannelEvent.BALANCE_PROOF_UPDATED,
        check_transfer_updated(channel_identifier, A, 2),
    )
    ev_handler.check()
