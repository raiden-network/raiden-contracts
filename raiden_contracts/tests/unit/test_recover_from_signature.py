import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3

from raiden_contracts.tests.utils.constants import EMPTY_ADDRESS
from raiden_contracts.utils.proofs import hash_balance_proof
from raiden_contracts.utils.signature import sign

# pylint: disable=E1120


@pytest.fixture
def signature_test_contract(deploy_tester_contract):
    return deploy_tester_contract("SignatureVerifyTest")


def test_verify(
    web3,
    token_network,
    signature_test_contract,
    get_accounts,
    create_channel,
    create_balance_proof,
):
    """ ECVerify.ecverify returns the correct address

    This test checks if the signature test contract returns the correct
    addresses on the balance hash signed by both ends of a channel """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 3)
    signature = balance_proof_A[3]
    balance_proof_hash = hash_balance_proof(
        token_network.address, int(web3.version.network), channel_identifier, *balance_proof_A[:3]
    )
    address = signature_test_contract.functions.verify(balance_proof_hash, signature).call()
    assert address == A

    balance_proof_B = create_balance_proof(channel_identifier, B, 0, 0, 0)
    signature = balance_proof_B[3]
    balance_proof_hash = hash_balance_proof(
        token_network.address, int(web3.version.network), channel_identifier, *balance_proof_B[:3]
    )
    address = signature_test_contract.functions.verify(balance_proof_hash, signature).call()
    assert address == B


def test_verify_fail(signature_test_contract, get_accounts, get_private_key):
    """ ECVerify.ecverify on failure cases

    the signature test contract returns the correct address on a correct
    message hash, returns a different address on a wrong message hash, and
    fails on a too long signature """
    A = get_accounts(1)[0]
    message_hash = Web3.soliditySha3(["string", "uint256"], ["hello", 5])
    signature = sign(get_private_key(A), message_hash, v=27)

    assert signature_test_contract.functions.verify(message_hash, signature).call() == A

    message_hash = Web3.soliditySha3(["string", "uint256"], ["hello", 6])
    assert signature_test_contract.functions.verify(message_hash, signature).call() != A

    signature2 = signature[:65] + bytes([2])
    with pytest.raises(TransactionFailed):
        signature_test_contract.functions.verify(message_hash, signature2).call()


def test_ecrecover_output(
    web3,
    token_network,
    signature_test_contract,
    get_accounts,
    create_channel,
    create_balance_proof,
):
    """ ecrecover returns the address that was used to sign a balance proof """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 3)
    signature = balance_proof_A[3]
    r = signature[:32]
    s = signature[32:64]
    v = signature[64:]
    balance_proof_hash = hash_balance_proof(
        token_network.address, int(web3.version.network), channel_identifier, *balance_proof_A[:3]
    )

    address = signature_test_contract.functions.verifyEcrecoverOutput(
        balance_proof_hash, r, s, int.from_bytes(v, byteorder="big")
    ).call()
    assert address == A


def test_ecrecover_output_zero(signature_test_contract, get_accounts, get_private_key):
    """ ecrecover returns 0 for an incorrect value of the v parameter """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    message_hash = Web3.soliditySha3(["string", "uint256"], ["hello", 5])
    signature = sign(privatekey, message_hash, v=27)

    assert (
        signature_test_contract.functions.verifyEcrecoverOutput(
            message_hash, signature[:32], signature[32:64], 2
        ).call()
        == EMPTY_ADDRESS
    )


def test_ecrecover_output_fail(signature_test_contract, get_accounts, get_private_key):
    """ ecrecover detects a wrong message content and returns zero """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    message_hash = Web3.soliditySha3(["string", "uint256"], ["hello", 5])
    signature = sign(privatekey, message_hash, v=27)

    assert (
        signature_test_contract.functions.verifyEcrecoverOutput(
            message_hash,
            signature[:32],
            signature[32:64],
            int.from_bytes(signature[64:], byteorder="big"),
        ).call()
        == A
    )

    message_hash2 = Web3.soliditySha3(["string", "uint256"], ["hello", 6])
    assert (
        signature_test_contract.functions.verifyEcrecoverOutput(
            message_hash2,
            signature[:32],
            signature[32:64],
            int.from_bytes(signature[64:], byteorder="big"),
        ).call()
        != A
    )
