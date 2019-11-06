from eth_abi import encode_single
from eth_typing.evm import HexAddress
from web3 import Web3

from raiden_contracts.constants import MessageTypeId

from .signature import sign


def hash_balance_data(transferred_amount: int, locked_amount: int, locksroot: bytes) -> bytes:
    # pylint: disable=E1120
    return Web3.solidityKeccak(
        abi_types=["uint256", "uint256", "bytes32"],
        values=[transferred_amount, locked_amount, locksroot],
    )


def eth_sign_hash_message(encoded_message: bytes) -> bytes:
    signature_prefix = "\x19Ethereum Signed Message:\n"
    return Web3.keccak(
        Web3.toBytes(text=signature_prefix)
        + Web3.toBytes(text=str(len(encoded_message)))
        + encoded_message
    )


def pack_balance_proof(
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    balance_hash: bytes,
    nonce: int,
    additional_hash: bytes,
    msg_type: MessageTypeId,
) -> bytes:
    return (
        Web3.toBytes(hexstr=token_network_address)
        + encode_single("uint256", chain_identifier)
        + encode_single("uint256", msg_type)
        + encode_single("uint256", channel_identifier)
        + balance_hash
        + encode_single("uint256", nonce)
        + additional_hash
    )


def pack_balance_proof_message(
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    msg_type: MessageTypeId,
    balance_hash: bytes,
    nonce: int,
    additional_hash: bytes,
    closing_signature: bytes,
) -> bytes:
    return (
        pack_balance_proof(
            token_network_address=token_network_address,
            chain_identifier=chain_identifier,
            channel_identifier=channel_identifier,
            balance_hash=balance_hash,
            nonce=nonce,
            additional_hash=additional_hash,
            msg_type=msg_type,
        )
        + closing_signature
    )


def pack_cooperative_settle_message(
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    participant1_address: HexAddress,
    participant1_balance: int,
    participant2_address: HexAddress,
    participant2_balance: int,
) -> bytes:
    return (
        Web3.toBytes(hexstr=token_network_address)
        + encode_single("uint256", chain_identifier)
        + encode_single("uint256", MessageTypeId.COOPERATIVE_SETTLE)
        + encode_single("uint256", channel_identifier)
        + Web3.toBytes(hexstr=participant1_address)
        + encode_single("uint256", participant1_balance)
        + Web3.toBytes(hexstr=participant2_address)
        + encode_single("uint256", participant2_balance)
    )


def pack_withdraw_message(
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    participant: HexAddress,
    amount_to_withdraw: int,
    expiration_block: int,
) -> bytes:
    return (
        Web3.toBytes(hexstr=token_network_address)
        + encode_single("uint256", chain_identifier)
        + encode_single("uint256", MessageTypeId.WITHDRAW)
        + encode_single("uint256", channel_identifier)
        + Web3.toBytes(hexstr=participant)
        + encode_single("uint256", amount_to_withdraw)
        + encode_single("uint256", expiration_block)
    )


def pack_reward_proof(
    monitoring_service_contract_address: HexAddress,
    chain_id: int,
    token_network_address: HexAddress,
    non_closing_participant: HexAddress,
    non_closing_signature: bytes,
    reward_amount: int,
) -> bytes:
    return (
        Web3.toBytes(hexstr=monitoring_service_contract_address)
        + encode_single("uint256", chain_id)
        + encode_single("uint256", MessageTypeId.MSReward)
        + Web3.toBytes(hexstr=token_network_address)
        + Web3.toBytes(hexstr=non_closing_participant)
        + non_closing_signature
        + encode_single("uint256", reward_amount)
    )


def sign_balance_proof(
    privatekey: str,
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    msg_type: MessageTypeId,
    balance_hash: bytes,
    nonce: int,
    additional_hash: bytes,
    v: int = 27,
) -> bytes:
    message_hash = eth_sign_hash_message(
        pack_balance_proof(
            token_network_address=token_network_address,
            chain_identifier=chain_identifier,
            channel_identifier=channel_identifier,
            balance_hash=balance_hash,
            nonce=nonce,
            additional_hash=additional_hash,
            msg_type=msg_type,
        )
    )

    return sign(privkey=privatekey, msg_hash=message_hash, v=v)


def sign_balance_proof_message(
    privatekey: str,
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    msg_type: MessageTypeId,
    balance_hash: bytes,
    nonce: int,
    additional_hash: bytes,
    closing_signature: bytes,
    v: int = 27,
) -> bytes:
    message_hash = eth_sign_hash_message(
        pack_balance_proof_message(
            token_network_address=token_network_address,
            chain_identifier=chain_identifier,
            channel_identifier=channel_identifier,
            msg_type=msg_type,
            balance_hash=balance_hash,
            nonce=nonce,
            additional_hash=additional_hash,
            closing_signature=closing_signature,
        )
    )

    return sign(privkey=privatekey, msg_hash=message_hash, v=v)


def sign_cooperative_settle_message(
    privatekey: str,
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    participant1_address: HexAddress,
    participant1_balance: int,
    participant2_address: HexAddress,
    participant2_balance: int,
    v: int = 27,
) -> bytes:
    message_hash = eth_sign_hash_message(
        pack_cooperative_settle_message(
            token_network_address=token_network_address,
            chain_identifier=chain_identifier,
            channel_identifier=channel_identifier,
            participant1_address=participant1_address,
            participant1_balance=participant1_balance,
            participant2_address=participant2_address,
            participant2_balance=participant2_balance,
        )
    )

    return sign(privkey=privatekey, msg_hash=message_hash, v=v)


def sign_withdraw_message(
    privatekey: str,
    token_network_address: HexAddress,
    chain_identifier: int,
    channel_identifier: int,
    participant: HexAddress,
    amount_to_withdraw: int,
    expiration_block: int,
    v: int = 27,
) -> bytes:
    message_hash = eth_sign_hash_message(
        pack_withdraw_message(
            token_network_address=token_network_address,
            chain_identifier=chain_identifier,
            channel_identifier=channel_identifier,
            participant=participant,
            amount_to_withdraw=amount_to_withdraw,
            expiration_block=expiration_block,
        )
    )

    return sign(privkey=privatekey, msg_hash=message_hash, v=v)


def sign_reward_proof(
    privatekey: str,
    monitoring_service_contract_address: HexAddress,
    chain_id: int,
    token_network_address: HexAddress,
    non_closing_participant: HexAddress,
    non_closing_signature: bytes,
    reward_amount: int,
    v: int = 27,
) -> bytes:
    packed_data = pack_reward_proof(
        monitoring_service_contract_address=monitoring_service_contract_address,
        chain_id=chain_id,
        token_network_address=token_network_address,
        non_closing_participant=non_closing_participant,
        non_closing_signature=non_closing_signature,
        reward_amount=reward_amount,
    )
    message_hash = eth_sign_hash_message(packed_data)

    return sign(privkey=privatekey, msg_hash=message_hash, v=v)


def sign_one_to_n_iou(
    privatekey: str,
    sender: HexAddress,
    receiver: HexAddress,
    amount: int,
    expiration_block: int,
    one_to_n_address: str,
    chain_id: int,
    v: int = 27,
) -> bytes:
    iou_hash = eth_sign_hash_message(
        Web3.toBytes(hexstr=one_to_n_address)
        + encode_single("uint256", chain_id)
        + encode_single("uint256", MessageTypeId.IOU)
        + Web3.toBytes(hexstr=sender)
        + Web3.toBytes(hexstr=receiver)
        + encode_single("uint256", amount)
        + encode_single("uint256", expiration_block)
    )
    return sign(privkey=privatekey, msg_hash=iou_hash, v=v)
