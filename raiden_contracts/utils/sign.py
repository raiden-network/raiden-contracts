from web3 import Web3
from .sign_utils import *


def sign_balance_proof(
        privatekey,
        channel_identifier,
        token_network_address,
        chain_identifier,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash):
    message_hash = Web3.soliditySha3([
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

    privatekey = hex(int.from_bytes(privatekey, byteorder='big'))

    return sign(privatekey, message_hash, v=27)
