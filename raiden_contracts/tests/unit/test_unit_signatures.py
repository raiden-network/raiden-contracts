import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.tests.utils import fake_bytes


def test_recover_address_from_withdraw_message(
        token_network_test_signatures,
        create_withdraw_signatures,
        create_channel_and_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    token_network = token_network_test_signatures
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
        token_network.address,
    )

    recovered_address_A = token_network.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_A,
    ).call()
    assert recovered_address_A == A

    recovered_address_B = token_network.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_B,
    ).call()
    assert recovered_address_B == B

    with pytest.raises(TransactionFailed):
        token_network.functions.recoverAddressFromWithdrawMessagePublic(
            channel_identifier,
            A,
            withdraw_A,
            fake_signature,
        ).call()

    wrong_participant = token_network.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        B,
        withdraw_A,
        signature_A,
    ).call()
    assert recovered_address_A != wrong_participant

    wrong_withdraw_value = token_network.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        1,
        signature_A,
    ).call()

    assert recovered_address_A != wrong_withdraw_value

    wrong_signature = token_network.functions.recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_B,
    ).call()

    assert recovered_address_A != wrong_signature


def test_recover_address_from_balance_proof(
        token_network_test_signatures,
        create_balance_proof,
        get_accounts,
):
    """ TokenNetwork can recover the signer's address from a balance proof

    This test checks that the TokenNetwork contract
    1) can recover the signer's address from a balance proof
    2) even when the signer and the balance proof's original sender are different
    3) recovers a wrong address when the balance proof is for a wrong token network
    """
    (A, B) = get_accounts(2)

    channel_identifier = 4
    balance_proof = create_balance_proof(
        channel_identifier,
        A,
        other_token_network=token_network_test_signatures,
    )

    balance_proof_wrong_token_network = create_balance_proof(
        channel_identifier,
        A,
    )

    balance_proof_other_signer = create_balance_proof(
        channel_identifier,
        A,
        signer=B,
        other_token_network=token_network_test_signatures,
    )

    assert A == token_network_test_signatures.functions.recoverAddressFromBalanceProofPublic(
        channel_identifier, *balance_proof).call()

    assert B == token_network_test_signatures.functions.recoverAddressFromBalanceProofPublic(
        channel_identifier,
        *balance_proof_other_signer,
    ).call()

    assert A != token_network_test_signatures.functions.recoverAddressFromBalanceProofPublic(
        channel_identifier, *balance_proof_wrong_token_network).call()


def test_recover_address_from_balance_proof_update(
        token_network_test_signatures,
        create_balance_proof,
        create_balance_proof_update_signature,
        get_accounts,
):
    """ TokenNetwork can recover the signer's address from a balance proof update

    This test checks that the TokenNetwork contract
    1) can recover the signer's address from a balance proof update
    2) recovers a wrong address if the balance proof update is for a wrong token network
    3) recovers a wrong address if the balance proof update is signed by the same secret key twice
    """
    (A, B) = get_accounts(2)
    other_token_network = token_network_test_signatures

    channel_identifier = 4
    balance_proof = create_balance_proof(
        channel_identifier,
        A,
        other_token_network=other_token_network,
    )
    balance_proof_update_signature = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof,
        other_token_network=other_token_network,
    )

    balance_proof_update_signature_wrong_token_network = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof,
    )

    balance_proof_signed_B = create_balance_proof(
        channel_identifier,
        B,
        other_token_network=other_token_network,
    )
    balance_proof_update_signature_wrong_signer = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_signed_B,
    )

    assert B == other_token_network.functions.recoverAddressFromBalanceProofUpdateMessagePublic(
        channel_identifier, *balance_proof, balance_proof_update_signature).call()

    assert B != other_token_network.functions.recoverAddressFromBalanceProofUpdateMessagePublic(
        channel_identifier,
        *balance_proof,
        balance_proof_update_signature_wrong_token_network,
    ).call()

    assert B != other_token_network.functions.recoverAddressFromBalanceProofUpdateMessagePublic(
        channel_identifier,
        *balance_proof,
        balance_proof_update_signature_wrong_signer,
    ).call()


@pytest.mark.skip(reason='Delayed to another milestone')
def test_recover_address_from_cooperative_settle_signature(
        token_network_test_signatures,
        create_cooperative_settle_signatures,
        get_accounts,
):
    (A, B) = get_accounts(2)
    other_token_network = token_network_test_signatures
    channel_identifier = 4
    fake_signature = fake_bytes(64)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B],
        channel_identifier,
        A,
        0,
        B,
        0,
        other_token_network=other_token_network,
    )
    assert A == other_token_network.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_A,
    ).call()

    assert B == other_token_network.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_B,
    ).call()

    assert B != other_token_network.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_A,
    ).call()

    assert A != other_token_network.functions.recoverAddressFromCooperativeSettleSignaturePublic(
        channel_identifier,
        A,
        0,
        B,
        0,
        signature_B,
    ).call()

    with pytest.raises(TransactionFailed):
        other_token_network.functions.recoverAddressFromCooperativeSettleSignaturePublic(
            channel_identifier,
            A,
            0,
            B,
            0,
            fake_signature,
        ).call()
