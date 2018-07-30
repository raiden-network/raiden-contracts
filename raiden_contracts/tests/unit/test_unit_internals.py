from itertools import chain, product

import pytest
from eth_tester.constants import UINT256_MIN, UINT256_MAX
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.tests.fixtures import fake_bytes
from web3.exceptions import ValidationError


def test_min_uses_usigned(token_network_test):
    """ Min cannot be called with negative values. """
    INVALID_VALUES = [-UINT256_MAX, -1]
    VALID_VALUES = [UINT256_MIN, UINT256_MAX, UINT256_MAX]

    all_invalid = chain(
        product(VALID_VALUES, INVALID_VALUES),
        product(INVALID_VALUES, VALID_VALUES),
    )

    for a, b in all_invalid:
        with pytest.raises(ValidationError):
            token_network_test.functions.minPublic(a, b).call()


def test_max_uses_usigned(token_network_test):

    INVALID_VALUES = [-UINT256_MAX, -1]
    VALID_VALUES = [UINT256_MIN, UINT256_MAX, UINT256_MAX]

    all_invalid = chain(
        product(VALID_VALUES, INVALID_VALUES),
        product(INVALID_VALUES, VALID_VALUES),
    )
    for a, b in all_invalid:
        with pytest.raises(ValidationError):
            token_network_test.functions.maxPublic(a, b).call()


def test_min(token_network_test):

    VALUES = [UINT256_MIN, 1, UINT256_MAX, UINT256_MAX]
    for a, b in product(VALUES, VALUES):
        assert token_network_test.functions.minPublic(a, b).call() == min(a, b)


def test_max(token_network_test):

    VALUES = [UINT256_MIN, 1, UINT256_MAX, UINT256_MAX]
    for a, b in product(VALUES, VALUES):
        assert token_network_test.functions.maxPublic(a, b).call() == max(a, b)


def test_verify_withdraw_signatures(
        token_network_test,
        create_withdraw_signatures,
        get_accounts,
):

    (A, B) = get_accounts(2)
    fake_signature = fake_bytes(64)
    channel_identifier = 4
    (signature_A, signature_B) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        1,
        token_network_test.address,
    )
    token_network_test.functions.verifyWithdrawSignaturesPublic(
        channel_identifier,
        A,
        B,
        1,
        signature_A,
        signature_B,
    ).call()

    with pytest.raises(TransactionFailed):
        token_network_test.functions.verifyWithdrawSignaturesPublic(
            channel_identifier,
            A,
            B,
            3,
            signature_B,
            signature_A,
        ).call()
    with pytest.raises(TransactionFailed):
        token_network_test.functions.verifyWithdrawSignaturesPublic(
            channel_identifier,
            A,
            B,
            3,
            signature_A,
            fake_signature,
        ).call()
    with pytest.raises(TransactionFailed):
        token_network_test.functions.verifyWithdrawSignaturesPublic(
            channel_identifier,
            A,
            B,
            3,
            fake_signature,
            signature_B,
        ).call()


def test_recover_address_from_withdraw_message(
        token_network_test,
        create_withdraw_signatures,
        create_channel_and_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    fake_signature = fake_bytes(64)
    deposit_A = 5
    deposit_B = 7
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    (signature_A, signature_B) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A,
        token_network_test.address,
    )

    recovered_address_A = token_network_test.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_A,
    ).call()
    assert recovered_address_A == A

    recovered_address_B = token_network_test.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_B,
    ).call()
    assert recovered_address_B == B

    with pytest.raises(TransactionFailed):
        token_network_test.functions.recoverAddressFromWithdrawMessagePublic(
            channel_identifier,
            A,
            withdraw_A,
            fake_signature,
        ).call()

    wrong_participant = token_network_test.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        B,
        withdraw_A,
        signature_A,
    ).call()
    assert recovered_address_A != wrong_participant

    wrong_withdraw_value = token_network_test.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        1,
        signature_A,
    ).call()

    assert recovered_address_A != wrong_withdraw_value

    wrong_signature = token_network_test.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_B,
    ).call()

    assert recovered_address_A != wrong_signature


def test_recover_address_from_balance_proof(
        token_network_test,
        create_balance_proof,
        get_accounts,
):
    (A, B) = get_accounts(2)

    channel_identifier = 4
    balance_proof = create_balance_proof(
        channel_identifier,
        A,
        other_token_network=token_network_test,
    )

    balance_proof_wrong_token_network = create_balance_proof(
        channel_identifier,
        A,
    )

    balance_proof_other_signer = create_balance_proof(
        channel_identifier,
        A,
        signer=B,
        other_token_network=token_network_test,
    )

    assert A == token_network_test.functions.recoverAddressFromBalanceProofPublic(
        channel_identifier, *balance_proof).call()

    assert B == token_network_test.functions.recoverAddressFromBalanceProofPublic(
        channel_identifier,
        *balance_proof_other_signer,
    ).call()

    assert A != token_network_test.functions.recoverAddressFromBalanceProofPublic(
        channel_identifier, *balance_proof_wrong_token_network).call()


def test_recover_address_from_balance_proof_update(
        token_network_test,
        create_balance_proof,
        create_balance_proof_update_signature,
        get_accounts,
):

    (A, B) = get_accounts(2)

    channel_identifier = 4
    balance_proof = create_balance_proof(
        channel_identifier,
        A,
        other_token_network=token_network_test,
    )
    balance_proof_update_signature = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof,
        other_token_network=token_network_test,
    )

    balance_proof_update_signature_wrong_token_network = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof,
    )

    balance_proof_signed_B = create_balance_proof(
        channel_identifier,
        B,
        other_token_network=token_network_test,
    )
    balance_proof_update_signature_wrong_signer = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_signed_B,
    )

    assert B == token_network_test.functions.recoverAddressFromBalanceProofUpdateMessagePublic(
        channel_identifier, *balance_proof, balance_proof_update_signature).call()

    assert B != token_network_test.functions.recoverAddressFromBalanceProofUpdateMessagePublic(
        channel_identifier,
        *balance_proof,
        balance_proof_update_signature_wrong_token_network,
    ).call()

    assert B != token_network_test.functions.recoverAddressFromBalanceProofUpdateMessagePublic(
        channel_identifier,
        *balance_proof,
        balance_proof_update_signature_wrong_signer,
    ).call()


def test_recover_address_from_cooperative_settle_signature(
        token_network_test,
        create_cooperative_settle_signatures,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = 4
    fake_signature = fake_bytes(64)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B],
        channel_identifier,
        A,
        0,
        B,
        0,
        other_token_network=token_network_test,
    )
    assert A == token_network_test.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_A,
    ).call()

    assert B == token_network_test.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_B,
    ).call()

    assert B != token_network_test.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_A,
    ).call()

    assert A != token_network_test.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_B,
    ).call()

    with pytest.raises(TransactionFailed):
        token_network_test.functions.recoverAddressFromCooperativeSettleSignaturePublic(
            channel_identifier,
            A,
            0,
            B,
            0,
            fake_signature,
        ).call()
