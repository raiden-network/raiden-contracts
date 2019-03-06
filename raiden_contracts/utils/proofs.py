from eth_abi import encode_single
from web3 import Web3

from raiden_contracts.constants import MessageTypeId

from .signature import sign


def hash_balance_data(transferred_amount, locked_amount, locksroot):
    # pylint: disable=E1120
    return Web3.soliditySha3(
        abi_types=['uint256', 'uint256', 'bytes32'],
        values=[transferred_amount, locked_amount, locksroot],
    )


def eth_sign_hash_message(encoded_message):
    signature_prefix = '\x19Ethereum Signed Message:\n'
    return Web3.sha3(
        Web3.toBytes(text=signature_prefix) +
        Web3.toBytes(text=str(len(encoded_message))) +
        encoded_message,
    )


def hash_balance_proof(
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
):
    return eth_sign_hash_message(
        Web3.toBytes(hexstr=token_network_address) +
        encode_single('uint256', chain_identifier) +
        encode_single('uint256', MessageTypeId.BALANCE_PROOF) +
        encode_single('uint256', channel_identifier) +
        balance_hash +
        encode_single('uint256', nonce) +
        additional_hash,
    )


def hash_balance_proof_update_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        balance_hash,
        nonce,
        additional_hash,
        closing_signature,
):
    return eth_sign_hash_message(
        Web3.toBytes(hexstr=token_network_address) +
        encode_single('uint256', chain_identifier) +
        encode_single('uint256', MessageTypeId.BALANCE_PROOF_UPDATE) +
        encode_single('uint256', channel_identifier) +
        balance_hash +
        encode_single('uint256', nonce) +
        additional_hash +
        closing_signature,
    )


def hash_cooperative_settle_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant1_address,
        participant1_balance,
        participant2_address,
        participant2_balance,
):
    return eth_sign_hash_message(
        Web3.toBytes(hexstr=token_network_address) +
        encode_single('uint256', chain_identifier) +
        encode_single('uint256', MessageTypeId.COOPERATIVE_SETTLE) +
        encode_single('uint256', channel_identifier) +
        Web3.toBytes(hexstr=participant1_address) +
        encode_single('uint256', participant1_balance) +
        Web3.toBytes(hexstr=participant2_address) +
        encode_single('uint256', participant2_balance),
    )


def hash_withdraw_message(
        token_network_address,
        chain_identifier,
        channel_identifier,
        participant,
        amount_to_withdraw,
):
    return eth_sign_hash_message(
        Web3.toBytes(hexstr=token_network_address) +
        encode_single('uint256', chain_identifier) +
        encode_single('uint256', MessageTypeId.WITHDRAW) +
        encode_single('uint256', channel_identifier) +
        Web3.toBytes(hexstr=participant) +
        encode_single('uint256', amount_to_withdraw),
    )


def hash_reward_proof(
        channel_identifier,
        reward_amount,
        token_network_address,
        chain_id,
        nonce):
    return eth_sign_hash_message(
        encode_single('uint256', channel_identifier) +
        encode_single('uint256', reward_amount) +
        Web3.toBytes(hexstr=token_network_address) +
        encode_single('uint256', chain_id) +
        encode_single('uint256', nonce),
    )


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
        token_network_address=token_network_address,
        chain_identifier=chain_identifier,
        channel_identifier=channel_identifier,
        balance_hash=balance_hash,
        nonce=nonce,
        additional_hash=additional_hash,
    )

    return sign(privkey=privatekey, msg=message_hash, v=v)


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
        token_network_address=token_network_address,
        chain_identifier=chain_identifier,
        channel_identifier=channel_identifier,
        balance_hash=balance_hash,
        nonce=nonce,
        additional_hash=additional_hash,
        closing_signature=closing_signature,
    )

    return sign(privkey=privatekey, msg=message_hash, v=v)


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
        token_network_address=token_network_address,
        chain_identifier=chain_identifier,
        channel_identifier=channel_identifier,
        participant1_address=participant1_address,
        participant1_balance=participant1_balance,
        participant2_address=participant2_address,
        participant2_balance=participant2_balance,
    )

    return sign(privkey=privatekey, msg=message_hash, v=v)


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
        token_network_address=token_network_address,
        chain_identifier=chain_identifier,
        channel_identifier=channel_identifier,
        participant=participant,
        amount_to_withdraw=amount_to_withdraw,
    )

    return sign(privkey=privatekey, msg=message_hash, v=v)


def sign_reward_proof(
        privatekey,
        channel_identifier,
        reward_amount,
        token_network_address,
        chain_id,
        nonce,
        v=27):
    message_hash = hash_reward_proof(
        channel_identifier=channel_identifier,
        reward_amount=reward_amount,
        token_network_address=token_network_address,
        chain_id=chain_id,
        nonce=nonce,
    )

    return sign(privkey=privatekey, msg=message_hash, v=v)


def sign_one_to_n_iou(
        privatekey,
        sender,
        receiver,
        amount,
        expiration,
        v=27,
):
    iou_hash = eth_sign_hash_message(
        Web3.toBytes(hexstr=sender) +
        Web3.toBytes(hexstr=receiver) +
        encode_single('uint256', amount) +
        encode_single('uint256', expiration),
    )
    return sign(privkey=privatekey, msg=iou_hash, v=v)
