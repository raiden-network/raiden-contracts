from web3 import Web3
from .sign_utils import sign


def hash_balance_data(transferred_amount, locked_amount, locksroot, additional_hash):
    return Web3.soliditySha3(
        ['uint256', 'uint256', 'bytes32', 'bytes32'],
        [transferred_amount, locked_amount, locksroot, additional_hash]
    )


def hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        nonce,
        balance_hash):
    return Web3.soliditySha3([
        'uint256',
        'bytes32',
        'uint256',
        'address',
        'uint256'
    ], [
        nonce,
        balance_hash,
        channel_identifier,
        token_network_address,
        chain_identifier
    ])


def sign_balance_proof(
        privatekey,
        token_network_address,
        chain_identifier,
        channel_identifier,
        nonce,
        balance_hash,
        v=27):
    message_hash = hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        nonce,
        balance_hash
    )

    return sign(privatekey, message_hash, v)
