from eth_abi import encode_single
from eth_typing.evm import HexAddress
from web3 import Web3
from web3.types import Nonce

from raiden_contracts.constants import MessageTypeId
from raiden_contracts.utils.type_aliases import (
    AdditionalHash,
    BalanceHash,
    BlockExpiration,
    ChainID,
    ChannelID,
    Locksroot,
    PrivateKey,
    Signature,
    TokenAmount,
)

from .signature import sign


def hash_balance_data(
    transferred_amount: TokenAmount, locked_amount: TokenAmount, locksroot: Locksroot
) -> BalanceHash:
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
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    balance_hash: BalanceHash,
    nonce: Nonce,
    additional_hash: AdditionalHash,
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
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    msg_type: MessageTypeId,
    balance_hash: BalanceHash,
    nonce: Nonce,
    additional_hash: AdditionalHash,
    closing_signature: Signature,
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
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    participant1_address: HexAddress,
    participant1_balance: TokenAmount,
    participant2_address: HexAddress,
    participant2_balance: TokenAmount,
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
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    participant: HexAddress,
    amount_to_withdraw: TokenAmount,
    expiration_block: BlockExpiration,
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
    chain_id: ChainID,
    token_network_address: HexAddress,
    non_closing_participant: HexAddress,
    non_closing_signature: Signature,
    reward_amount: TokenAmount,
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
    privatekey: PrivateKey,
    token_network_address: HexAddress,
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    msg_type: MessageTypeId,
    balance_hash: BalanceHash,
    nonce: Nonce,
    additional_hash: AdditionalHash,
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
    privatekey: PrivateKey,
    token_network_address: HexAddress,
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    msg_type: MessageTypeId,
    balance_hash: BalanceHash,
    nonce: Nonce,
    additional_hash: AdditionalHash,
    closing_signature: Signature,
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


def sign_withdraw_message(
    privatekey: PrivateKey,
    token_network_address: HexAddress,
    chain_identifier: ChainID,
    channel_identifier: ChannelID,
    participant: HexAddress,
    amount_to_withdraw: TokenAmount,
    expiration_block: BlockExpiration,
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
    privatekey: PrivateKey,
    monitoring_service_contract_address: HexAddress,
    chain_id: ChainID,
    token_network_address: HexAddress,
    non_closing_participant: HexAddress,
    non_closing_signature: Signature,
    reward_amount: TokenAmount,
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
    privatekey: PrivateKey,
    sender: HexAddress,
    receiver: HexAddress,
    amount: TokenAmount,
    expiration_block: BlockExpiration,
    one_to_n_address: HexAddress,
    chain_id: ChainID,
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
