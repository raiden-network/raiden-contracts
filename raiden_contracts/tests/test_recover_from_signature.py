import pytest
from ethereum import tester
from web3 import Web3
from raiden_contracts.utils.sign import hash_balance_proof
from .fixtures.config import empty_address
from raiden_contracts.utils.sign_utils import sign


@pytest.fixture
def signature_test_contract(chain, create_contract, custom_token, secret_registry):
    SignatureVerifyTest = chain.provider.get_contract_factory('SignatureVerifyTest')
    signature_test_contract = create_contract(SignatureVerifyTest, [])

    return signature_test_contract


def test_verify(
        web3,
        token_network,
        signature_test_contract,
        get_accounts,
        create_channel,
        create_balance_proof
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 3)
    signature = balance_proof_A[3]
    balance_proof_hash = hash_balance_proof(
        token_network.address,
        int(web3.version.network),
        channel_identifier,
        *balance_proof_A[:3]
    )
    address = signature_test_contract.call().verify(balance_proof_hash, signature)
    assert address == A

    balance_proof_B = create_balance_proof(channel_identifier, B, 0, 0, 0)
    signature = balance_proof_B[3]
    balance_proof_hash = hash_balance_proof(
        token_network.address,
        int(web3.version.network),
        channel_identifier,
        *balance_proof_B[:3]
    )
    address = signature_test_contract.call().verify(balance_proof_hash, signature)
    assert address == B


def test_verify_fail(signature_test_contract, get_accounts, get_private_key):
    (A, B) = get_accounts(2)
    message_hash = Web3.soliditySha3(['string', 'uint256'], ['hello', 5])
    signature = sign(get_private_key(A), message_hash, v=27)

    assert signature_test_contract.call().verify(message_hash, signature) == A

    message_hash = Web3.soliditySha3(['string', 'uint256'], ['hello', 6])
    assert signature_test_contract.call().verify(message_hash, signature) != A

    signature2 = signature[:65] + bytes([2])
    with pytest.raises(tester.TransactionFailed):
        signature_test_contract.call().verify(message_hash, signature2)


def test_ecrecover_output(
        web3,
        token_network,
        signature_test_contract,
        get_accounts, create_channel,
        create_balance_proof
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 3)
    signature = balance_proof_A[3]
    r = signature[:32]
    s = signature[32:64]
    v = signature[64:]
    balance_proof_hash = hash_balance_proof(
        token_network.address,
        int(web3.version.network),
        channel_identifier,
        *balance_proof_A[:3]
    )

    address = signature_test_contract.call().verifyEcrecoverOutput(
        balance_proof_hash,
        r,
        s,
        int.from_bytes(v, byteorder='big')
    )
    assert address == A


def test_ecrecover_output_zero(signature_test_contract, get_accounts, get_private_key):
    """ ecrecover returns 0 due to an error caused by an incorrect value of the v parameter """
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    message_hash = Web3.soliditySha3(['string', 'uint256'], ['hello', 5])
    signature = sign(privatekey, message_hash, v=27)

    assert signature_test_contract.call().verifyEcrecoverOutput(
        message_hash,
        signature[:32],
        signature[32:64],
        2
    ) == empty_address


def test_ecrecover_output_fail(signature_test_contract, get_accounts, get_private_key):
    A = get_accounts(1)[0]
    privatekey = get_private_key(A)
    message_hash = Web3.soliditySha3(['string', 'uint256'], ['hello', 5])
    signature = sign(privatekey, message_hash, v=27)

    assert signature_test_contract.call().verifyEcrecoverOutput(
        message_hash,
        signature[:32],
        signature[32:64],
        int.from_bytes(signature[64:], byteorder='big')
    ) == A

    message_hash2 = Web3.soliditySha3(['string', 'uint256'], ['hello', 6])
    assert signature_test_contract.call().verifyEcrecoverOutput(
        message_hash2,
        signature[:32],
        signature[32:64],
        int.from_bytes(signature[64:], byteorder='big')
    ) != A
