from web3 import Web3
from .sign_utils import sign


def hash_balance_data(transferred_amount, locked_amount, locksroot):
    return Web3.soliditySha3(
        ['uint256', 'uint256', 'bytes32'],
        [transferred_amount, locked_amount, locksroot],
    )


def hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
):
    return Web3.soliditySha3([
        'bytes32',
        'uint256',
        'bytes32',
        'uint256',
        'address',
        'uint256',
    ], [
        balance_hash,
        nonce,
        additional_hash,
        channel_identifier,
        token_network_address,
        chain_identifier,
    ])


def hash_balance_proof_update_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
        closing_signature,
):
    return Web3.soliditySha3([
        'bytes32',
        'uint256',
        'bytes32',
        'uint256',
        'address',
        'uint256',
        'bytes',
    ], [
        balance_hash,
        nonce,
        additional_hash,
        channel_identifier,
        token_network_address,
        chain_identifier,
        closing_signature,
    ])


def hash_cooperative_settle_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant1_address,
        participant1_balance,
        participant2_address,
        participant2_balance,
):
    return Web3.soliditySha3([
        'address',
        'uint256',
        'address',
        'uint256',
        'uint256',
        'address',
        'uint256',
    ], [
        participant1_address,
        participant1_balance,
        participant2_address,
        participant2_balance,
        channel_identifier,
        token_network_address,
        chain_identifier,
    ])


def hash_withdraw_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant,
        amount_to_withdraw,
):
    return Web3.soliditySha3([
        'address',
        'uint256',
        'uint256',
        'address',
        'uint256',
    ], [
        participant,
        amount_to_withdraw,
        channel_identifier,
        token_network_address,
        chain_identifier,
    ])


def hash_reward_proof(
        channel_identifier,
        reward_amount,
        token_network_address,
        chain_id,
        nonce):
    return Web3.soliditySha3([
        'uint256',
        'uint256',
        'address',
        'uint256',
        'uint256',
    ], [
        channel_identifier,
        reward_amount,
        token_network_address,
        chain_id,
        nonce,
    ])


def sign_balance_proof(
        privatekey,
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
        v=27,
):
    message_hash = hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
    )

    return sign(privatekey, message_hash, v)


def sign_balance_proof_update_message(
        privatekey,
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
        closing_signature,
        v=27,
):
    message_hash = hash_balance_proof_update_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
        closing_signature,
    )

    return sign(privatekey, message_hash, v)


def sign_cooperative_settle_message(
        privatekey,
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant1_address,
        participant1_balance,
        participant2_address,
        participant2_balance,
        v=27,
):
    message_hash = hash_cooperative_settle_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant1_address,
        participant1_balance,
        participant2_address,
        participant2_balance,
    )

    return sign(privatekey, message_hash, v)


def sign_withdraw_message(
        privatekey,
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant,
        amount_to_withdraw,
        v=27,
):
    message_hash = hash_withdraw_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant,
        amount_to_withdraw,
    )

    return sign(privatekey, message_hash, v)


def sign_reward_proof(
        privatekey,
        channel_identifier,
        reward_amount,
        token_network_address,
        chain_id,
        nonce,
        v=27):
    message_hash = hash_reward_proof(
        channel_identifier,
        reward_amount,
        token_network_address,
        chain_id,
        nonce,
    )

    return sign(privatekey, message_hash, v)
