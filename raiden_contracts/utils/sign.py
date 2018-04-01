from web3 import Web3
from .sign_utils import sign


def hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash):
    return Web3.soliditySha3([
        'uint64',
        'uint256',
        'bytes32',
        'uint256',
        'address',
        'uint256',
        'bytes32'
    ], [
        nonce,
        transferred_amount,
        locksroot,
        channel_identifier,
        token_network_address,
        chain_identifier,
        additional_hash
    ])


def sign_balance_proof(
        privatekey,
        token_network_address,
        chain_identifier,
        channel_identifier,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash,
        v=27):
    message_hash = hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash
    )

    return sign(privatekey, message_hash, v)
