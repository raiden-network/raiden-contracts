from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import EMPTY_ADDRESS, MessageTypeId
from raiden_contracts.utils.proofs import eth_sign_hash_message, pack_balance_proof
from raiden_contracts.utils.signature import sign

# pylint: disable=E1120


@pytest.fixture
def signature_test_contract(deploy_tester_contract: Callable) -> Contract:
    return deploy_tester_contract("SignatureVerifyTest")


def test_verify(
    web3: Web3,
    token_network: Contract,
    signature_test_contract: Contract,
    get_accounts: Callable,
    create_channel: Callable,
    create_balance_proof: Callable,
) -> None:
    """ ECVerify.ecverify returns the correct address

    This test checks if the signature test contract returns the correct
    addresses on the balance hash signed by both ends of a channel """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 3)
    signature = balance_proof_A.original_signature
    balance_proof_hash = eth_sign_hash_message(
        pack_balance_proof(
            token_network_address=token_network.address,
            chain_identifier=web3.eth.chainId,
            channel_identifier=channel_identifier,
            balance_hash=balance_proof_A.balance_hash,
            nonce=balance_proof_A.nonce,
            additional_hash=balance_proof_A.additional_hash,
            msg_type=MessageTypeId.BALANCE_PROOF,
        )
    )
    address = signature_test_contract.functions.verify(balance_proof_hash, signature).call()
    assert address == A

    balance_proof_B = create_balance_proof(channel_identifier, B, 0, 0, 0)
    signature = balance_proof_B.original_signature
    balance_proof_hash = eth_sign_hash_message(
        pack_balance_proof(
            token_network_address=token_network.address,
            chain_identifier=web3.eth.chainId,
            channel_identifier=channel_identifier,
            balance_hash=balance_proof_B.balance_hash,
            nonce=balance_proof_B.nonce,
            additional_hash=balance_proof_B.additional_hash,
            msg_type=MessageTypeId.BALANCE_PROOF,
        )
    )
    address = signature_test_contract.functions.verify(balance_proof_hash, signature).call()
    assert address == B


def test_verify_fail(
    signature_test_contract: Contract, get_accounts: Callable, get_private_key: Callable
) -> None:
    """ ECVerify.ecverify on failure cases

    the signature test contract returns the correct address on a correct
    message hash, returns a different address on a wrong message hash, and
    fails on a too long signature """
    A = get_accounts(1)[0]
    message_hash = Web3.solidityKeccak(["string", "uint256"], ["hello", 5])
    signature = sign(get_private_key(A), message_hash, v=27)

    assert signature_test_contract.functions.verify(message_hash, signature).call() == A

    message_hash = Web3.solidityKeccak(["string", "uint256"], ["hello", 6])
    assert signature_test_contract.functions.verify(message_hash, signature).call() != A

    signature2 = signature[:65] + bytes([2])
    with pytest.raises(TransactionFailed):
        signature_test_contract.functions.verify(message_hash, signature2).call()


def test_ecrecover_output(
    web3: Web3,
    token_network: Contract,
    signature_test_contract: Contract,
    get_accounts: Callable,
    create_channel: Callable,
    create_balance_proof: Callable,
) -> None:
    """ ecrecover returns the address that was used to sign a balance proof """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 3)
    signature = balance_proof_A.original_signature
    r = signature[:32]
    s = signature[32:64]
    v = signature[64:]
    balance_proof_hash = eth_sign_hash_message(
        pack_balance_proof(
            token_network_address=token_network.address,
            chain_identifier=web3.eth.chainId,
            channel_identifier=channel_identifier,
            balance_hash=balance_proof_A.balance_hash,
            nonce=balance_proof_A.nonce,
            additional_hash=balance_proof_A.additional_hash,
            msg_type=MessageTypeId.BALANCE_PROOF,
        )
    )

    address = signature_test_contract.functions.verifyEcrecoverOutput(
        balance_proof_hash, r, s, int.from_bytes(v, byteorder="big")
    ).call()
    assert address == A


def test_ecrecover_output_zero(
    signature_test_contract: Contract, get_accounts: Callable, get_private_key: Callable
) -> None:
    """ ecrecover returns 0 for an incorrect value of the v parameter """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    message_hash = Web3.solidityKeccak(["string", "uint256"], ["hello", 5])
    signature = sign(privatekey, message_hash, v=27)

    assert (
        signature_test_contract.functions.verifyEcrecoverOutput(
            message_hash, signature[:32], signature[32:64], 2
        ).call()
        == EMPTY_ADDRESS
    )


def test_ecrecover_output_fail(
    signature_test_contract: Contract, get_accounts: Callable, get_private_key: Callable
) -> None:
    """ ecrecover detects a wrong message content and returns zero """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    message_hash = Web3.solidityKeccak(["string", "uint256"], ["hello", 5])
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

    message_hash2 = Web3.solidityKeccak(["string", "uint256"], ["hello", 6])
    assert (
        signature_test_contract.functions.verifyEcrecoverOutput(
            message_hash2,
            signature[:32],
            signature[32:64],
            int.from_bytes(signature[64:], byteorder="big"),
        ).call()
        != A
    )


def test_sign_not_bytes(get_private_key: Callable, get_accounts: Callable) -> None:
    """ sign() raises when message is not bytes """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    with pytest.raises(TypeError):
        sign(privatekey, "a" * 32, v=27)  # type: ignore


def test_sign_not_32_bytes(get_private_key: Callable, get_accounts: Callable) -> None:
    """ sign() raises when message is not exactly 32 bytes """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    with pytest.raises(ValueError):
        sign(privatekey, bytes("a" * 31, "ascii"), v=27)


def test_sign_privatekey_not_string(get_private_key: Callable, get_accounts: Callable) -> None:
    """ sign() raises when the private key is not a string """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    with pytest.raises(TypeError):
        sign(bytes(privatekey, "ascii"), bytes("a" * 32, "ascii"), v=27)  # type: ignore


def test_sign_wrong_v(get_private_key: Callable, get_accounts: Callable) -> None:
    """ sign() raises when the private key is not a string """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    with pytest.raises(ValueError):
        sign(privatekey, bytes("a" * 32, "ascii"), v=22)
