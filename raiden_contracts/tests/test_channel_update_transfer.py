from collections import namedtuple
from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    EMPTY_ADDRESS,
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelState,
    MessageTypeId,
)
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    ChannelValues,
    call_and_transact,
    fake_bytes,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.events import check_transfer_updated


def test_update_call(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """Call updateNonClosingBalanceProof() with various wrong arguments"""
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 15, B)
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    # Failure with the zero address instead of A's address
    with pytest.raises(TransactionFailed, match="TN: participant address zero"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            EMPTY_ADDRESS,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": C})

    # Failure with the zero address instead of B's address
    with pytest.raises(TransactionFailed, match="TN: partner address zero"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            EMPTY_ADDRESS,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": C})

    # Failure with the zero signature
    with pytest.raises(TransactionFailed):  # TODO: sig check
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            EMPTY_SIGNATURE,
        ).call({"from": C})

    # Failure with the empty balance hash
    with pytest.raises(TransactionFailed, match="TN/update: balance hash is zero"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            EMPTY_BALANCE_HASH,
            balance_proof_A.nonce,
            balance_proof_A.additional_hash,
            balance_proof_A.original_signature,
            balance_proof_update_signature_B,
        ).call({"from": C})

    # Failure with nonce zero
    with pytest.raises(TransactionFailed, match="TN/update: nonce is zero"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_A.balance_hash,
            0,
            balance_proof_A.additional_hash,
            balance_proof_A.original_signature,
            balance_proof_update_signature_B,
        ).call({"from": C})

    # Failure with the empty signature
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_A.balance_hash,
            balance_proof_A.nonce,
            balance_proof_A.additional_hash,
            EMPTY_SIGNATURE,
            balance_proof_update_signature_B,
        ).call({"from": C})

    # See a success to make sure the above failures are not spurious
    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_A.balance_hash,
            balance_proof_A.nonce,
            balance_proof_A.additional_hash,
            balance_proof_A.original_signature,
            balance_proof_update_signature_B,
        ),
        {"from": C},
    )


def test_update_nonexistent_fail(
    get_accounts: Callable,
    token_network: Contract,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """updateNonClosingBalanceProof() on a not-yet openned channel should fail"""
    (A, B, C) = get_accounts(3)
    channel_identifier = 1

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert settle_block_number == 0
    assert state == ChannelState.NONEXISTENT

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    with pytest.raises(TransactionFailed, match="TN/update: channel id mismatch"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": C})


def test_update_notclosed_fail(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """updateNonClosingBalanceProof() on an Opened channel should fail"""
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 25, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert settle_block_number > 0
    assert state == ChannelState.OPENED

    with pytest.raises(TransactionFailed, match="TN/update: channel not closed"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": C})


def test_update_wrong_nonce_fail(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    update_state_tests: Callable,
) -> None:
    (A, B, Delegate) = get_accounts(3)
    settle_timeout = 6
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, "02"))
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )
    txn_hash1 = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )

    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": Delegate},
    )

    # updateNonClosingBalanceProof should fail for the same nonce as provided previously
    with pytest.raises(TransactionFailed, match="TN: nonce reused"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": Delegate})
    balance_proof_A_same_nonce = create_balance_proof(
        channel_identifier, A, 12, 2, balance_proof_A.nonce, fake_bytes(32, "03")
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_same_nonce._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": Delegate})

    balance_proof_A_lower_nonce = create_balance_proof(
        channel_identifier, A, 10, 0, 4, fake_bytes(32, "02")
    )

    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A_lower_nonce._asdict(),
    )
    with pytest.raises(TransactionFailed, match="TN: nonce reused"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_lower_nonce._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": A})

    update_state_tests(
        channel_identifier,
        A,
        balance_proof_A,
        B,
        balance_proof_B,
        settle_timeout,
        txn_hash1,
    )


def test_update_wrong_signatures(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """updateNonClosingBalanceProof() should fail with wrong signatures"""
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 25, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_A_fake = create_balance_proof(
        channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"), signer=C
    )

    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )
    balance_proof_update_signature_B_fake = create_balance_proof_countersignature(
        participant=C,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    # Close the channel so updateNonClosingBalanceProof() is possible
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A_fake._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": C})
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B_fake,
        ).call({"from": C})

    # See a success to make sure that the above failures are not spurious
    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": C},
    )


def test_update_channel_state(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    update_state_tests: Callable,
    txn_cost: Callable,
) -> None:
    """A successful updateNonClosingBalanceProof() call should not change token/ETH balances"""
    (A, B, Delegate) = get_accounts(3)
    settle_timeout = 6
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, "02"))
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    txn_hash1 = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )

    pre_eth_balance_A = web3.eth.get_balance(A)
    pre_eth_balance_B = web3.eth.get_balance(B)
    pre_eth_balance_delegate = web3.eth.get_balance(Delegate)
    pre_eth_balance_contract = web3.eth.get_balance(token_network.address)
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_delegate = custom_token.functions.balanceOf(Delegate).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    txn_hash = call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": Delegate},
    )

    # Test that no balances have changed.
    # There are no transfers to be made in updateNonClosingBalanceProof.
    assert web3.eth.get_balance(A) == pre_eth_balance_A
    assert web3.eth.get_balance(B) == pre_eth_balance_B
    assert web3.eth.get_balance(Delegate) == pre_eth_balance_delegate - txn_cost(txn_hash)
    assert web3.eth.get_balance(token_network.address) == pre_eth_balance_contract
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
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """Calls to updateNonClosingBalanceProof() fail with the zero nonce"""
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]
    balance_proof_A = create_balance_proof(channel_identifier, A, 0, 0, 0)
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    with pytest.raises(TransactionFailed, match="TN/update: balance hash is zero"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            EMPTY_SIGNATURE,
        ).call({"from": B})

    with pytest.raises(TransactionFailed, match="TN/update: nonce is zero"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": B})


def test_update_allowed_after_settlement_period(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    web3: Web3,
) -> None:
    """updateNonClosingBalanceProof can be called after the settlement period."""
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, "02"))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, "02"))
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )
    mine_blocks(web3, settle_timeout + 1)
    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A._asdict().values(),
        balance_proof_update_signature_B,
    ).call({"from": A})


def test_update_not_allowed_for_the_closing_address(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """Closing address cannot call updateNonClosingBalanceProof."""
    (A, B, M) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    # Some balance proof from B
    balance_proof_B_0 = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, "02"))
    closing_sig_A_0 = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B_0._asdict(),
    )

    # Later balance proof, higher transferred amount, higher nonce
    balance_proof_B_1 = create_balance_proof(channel_identifier, B, 10, 0, 4, fake_bytes(32, "02"))

    # B's signature on the update message is valid
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_B_1._asdict(),
    )

    # A closes with the first balance proof
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            *balance_proof_B_0._asdict().values(),
            closing_sig_A_0,
        ),
        {"from": A},
    )

    # Someone wants to update with later balance proof - not possible
    with pytest.raises(TransactionFailed, match="TN/update: invalid closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": A})
    with pytest.raises(TransactionFailed, match="TN/update: invalid closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": B})
    with pytest.raises(TransactionFailed, match="TN/update: invalid closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_B_1._asdict().values(),
            balance_proof_update_signature_B,
        ).call({"from": M})


def test_update_invalid_balance_proof_arguments(
    token_network: Contract,
    token_network_test_utils: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """updateNonClosingBalanceProof() should fail on balance proofs with various wrong params"""
    (A, B, C) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    balance_proof = namedtuple(
        "balance_proof", ["balance_hash", "nonce", "additional_hash", "signature"]
    )

    #  Create valid balance_proof
    balance_proof_valid = balance_proof(
        *create_balance_proof(channel_identifier, A, 10, 0, 2, fake_bytes(32, "02"))
        ._asdict()
        .values()
    )

    # And a valid nonclosing_signature
    valid_balance_proof_update_signature = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        *balance_proof_valid._asdict().values(),
    )

    #  We test invalid balance proof arguments with valid signatures

    #  Create balance_proof for invalid token_network
    balance_proof_invalid_token_network = balance_proof(
        *create_balance_proof(
            channel_identifier,
            A,
            10,
            0,
            2,
            fake_bytes(32, "02"),
            other_token_network=token_network_test_utils,
        )
        ._asdict()
        .values()
    )

    signature_invalid_token_network = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
        other_token_network=token_network_test_utils,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_token_network._asdict().values(),
            signature_invalid_token_network,
        ).call({"from": B})

    #  Create balance_proof for invalid channel participant
    balance_proof_invalid_channel_participant = balance_proof(
        *create_balance_proof(channel_identifier, C, 10, 0, 2, fake_bytes(32, "02"))
        ._asdict()
        .values()
    )

    signature_invalid_channel_participant = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_channel_participant._asdict().values(),
            signature_invalid_channel_participant,
        ).call({"from": B})

    #  Create balance_proof for invalid channel identifier
    balance_proof_invalid_channel_identifier = balance_proof(
        *create_balance_proof(channel_identifier + 1, A, 10, 0, 2, fake_bytes(32, "02"))
        ._asdict()
        .values()
    )

    signature_invalid_channel_identifier = create_balance_proof_countersignature(
        B,
        channel_identifier + 1,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_invalid_channel_identifier._asdict().values(),
            signature_invalid_channel_identifier,
        ).call({"from": B})

    signature_invalid_balance_hash = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash[::-1],
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash[::-1],  # invalid balance_hash
            balance_proof_valid.nonce,
            balance_proof_valid.additional_hash,
            balance_proof_valid.signature,
            signature_invalid_balance_hash,
        ).call({"from": B})

    signature_invalid_nonce = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        1,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )

    with pytest.raises(TransactionFailed, match="TN/update: invalid closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash,
            1,  # invalid nonce
            balance_proof_valid.additional_hash,
            balance_proof_valid.signature,
            signature_invalid_nonce,
        ).call({"from": B})

    signature_invalid_additional_hash = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash[::-1],
        balance_proof_valid.signature,
    )

    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash,
            balance_proof_valid.nonce,
            fake_bytes(32, "02"),  # invalid additional_hash
            balance_proof_valid.signature,
            signature_invalid_additional_hash,
        ).call({"from": B})

    signature_invalid_closing_signature = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature[::-1],
    )

    with pytest.raises(TransactionFailed):  # TODO: fixme
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            balance_proof_valid.balance_hash,
            balance_proof_valid.nonce,
            balance_proof_valid.additional_hash,
            balance_proof_valid.signature,
            signature_invalid_closing_signature[::-1],  # invalid non-closing signature
        ).call({"from": B})

    # Call with same balance_proof and signature on valid arguments still works

    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            valid_balance_proof_update_signature,
        ),
        {"from": B},
    )


def test_update_signature_on_invalid_arguments(
    token_network: Contract,
    token_network_test_utils: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """Call updateNonClosingBalanceProof with signature on invalid argument fails"""
    (A, B, C) = get_accounts(3)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof = namedtuple(
        "balance_proof", ["balance_hash", "nonce", "additional_hash", "signature"]
    )

    # Close channel
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    #  Create valid balance_proof
    balance_proof_valid = balance_proof(
        *create_balance_proof(
            channel_identifier, A, 10, 0, 2, fake_bytes(32, "02"), fake_bytes(32, "02")
        )
        ._asdict()
        .values()
    )

    signature_invalid_token_network_address = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        *balance_proof_valid._asdict().values(),
        other_token_network=token_network_test_utils,  # invalid token_network_address
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_token_network_address,
        ).call({"from": B})

    signature_invalid_participant = create_balance_proof_countersignature(
        C,  # invalid signer
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_participant,
        ).call({"from": B})

    signature_invalid_channel_identifier = create_balance_proof_countersignature(
        B,
        channel_identifier + 1,  # invalid channel_identifier
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_channel_identifier,
        ).call({"from": B})

    signature_invalid_balance_hash = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash[::-1],  # invalid balance_hash
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_balance_hash,
        ).call({"from": B})

    signature_invalid_nonce = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        1,  # invalid nonce
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_nonce,
        ).call({"from": B})

    signature_invalid_additional_hash = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        b"\x00" * 32,  # invalid additional_hash
        balance_proof_valid.signature,
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_additional_hash,
        ).call({"from": B})

    signature_invalid_closing_signature = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        balance_proof_valid.balance_hash,
        balance_proof_valid.nonce,
        balance_proof_valid.additional_hash,
        balance_proof_valid.signature[::-1],
    )
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            signature_invalid_closing_signature,
        ).call({"from": B})

    # Call with same balance_proof and signature on valid arguments works
    balance_proof_update_signature = create_balance_proof_countersignature(
        B,
        channel_identifier,
        MessageTypeId.BALANCE_PROOF_UPDATE,
        *balance_proof_valid._asdict().values(),
    )
    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_valid._asdict().values(),
            balance_proof_update_signature,
        ),
        {"from": B},
    )


def test_update_replay_reopened_channel(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """updateNonClosingBalanceProof() should refuse a balance proof with a stale channel id"""
    (A, B) = get_accounts(2)
    nonce_B = 5
    values_A = ChannelValues(deposit=10, transferred=0)
    values_B = ChannelValues(deposit=20, transferred=15)

    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, B, values_B.deposit, A)
    balance_proof_B = create_balance_proof(
        channel_identifier1,
        B,
        values_B.transferred,
        values_B.locked_amounts.locked,
        nonce_B,
        values_B.locksroot,
    )
    balance_proof_update_signature_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier1,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_B._asdict(),
    )

    closing_sig = create_close_signature_for_no_balance_proof(B, channel_identifier1)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier1,
            A,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": B},
    )

    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier1,
            B,
            A,
            *balance_proof_B._asdict().values(),
            balance_proof_update_signature_A,
        ),
        {"from": A},
    )

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier1,
            A,
            values_A.transferred,
            values_A.locked_amounts.locked,
            values_A.locksroot,
            B,
            values_B.transferred,
            values_B.locked_amounts.locked,
            values_B.locksroot,
        ),
        {"from": A},
    )

    # Make sure we cannot update balance proofs after settleChannel is called
    with pytest.raises(TransactionFailed, match="TN/update: channel id mismatch"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier1,
            B,
            A,
            *balance_proof_B._asdict().values(),
            balance_proof_update_signature_A,
        ).call({"from": A})

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, B, values_B.deposit, A)
    closing_sig = create_close_signature_for_no_balance_proof(B, channel_identifier2)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier2,
            A,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": B},
    )

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed, match="TN/update: invalid non-closing sig"):
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier2,
            B,
            A,
            *balance_proof_B._asdict().values(),
            balance_proof_update_signature_A,
        ).call({"from": A})

    # Correct channel_identifier must work
    balance_proof_B2 = create_balance_proof(
        channel_identifier2,
        B,
        values_B.transferred,
        values_B.locked_amounts.locked,
        nonce_B,
        values_B.locksroot,
    )
    balance_proof_update_signature_A2 = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier2,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_B2._asdict(),
    )

    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier2,
            B,
            A,
            *balance_proof_B2._asdict().values(),
            balance_proof_update_signature_A2,
        ),
        {"from": A},
    )


def test_update_channel_event(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    event_handler: Callable,
) -> None:
    """Successful updateNonClosingBalanceProof() emit BALANCE_PROOF_UPDATED events"""
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    channel_deposit(channel_identifier, B, deposit_B, A)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3)
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 1)
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )

    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )
    txn_hash = call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": B},
    )

    ev_handler.add(
        txn_hash,
        ChannelEvent.BALANCE_PROOF_UPDATED,
        check_transfer_updated(channel_identifier, A, 1, balance_proof_A.balance_hash),
    )
    ev_handler.check()

    # Test event for second balance proof update
    balance_proof_A2 = create_balance_proof(channel_identifier, A, 4, 0, 2)
    balance_proof_update_signature_B2 = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A2._asdict(),
    )
    txn_hash = call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A2._asdict().values(),
            balance_proof_update_signature_B2,
        ),
        {"from": B},
    )

    ev_handler.add(
        txn_hash,
        ChannelEvent.BALANCE_PROOF_UPDATED,
        check_transfer_updated(channel_identifier, A, 2, balance_proof_A2.balance_hash),
    )
    ev_handler.check()
