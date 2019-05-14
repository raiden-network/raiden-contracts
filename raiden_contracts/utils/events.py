from typing import Any, Callable, Dict, List

from raiden_contracts.utils.type_aliases import Address


def check_secret_revealed(secrethash: bytes, secret: bytes) -> Callable[..., Any]:
    def get(event: Any) -> Any:
        assert event["args"]["secrethash"] == secrethash
        assert event["args"]["secret"] == secret

    return get


def check_secrets_revealed(secrethashes: List[bytes], secrets: List[bytes]) -> Callable[..., Any]:
    def get(event: Any) -> Any:
        assert event["args"]["secrethash"] in secrethashes
        assert event["args"]["secret"] in secrets

    return get


def check_token_network_created(
    token_address: Address, token_network_address: Address
) -> Callable[..., None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["token_address"] == token_address
        assert event["args"]["token_network_address"] == token_network_address

    return get


def check_address_registered(eth_address: Address, endpoint: str) -> Callable[..., Any]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["eth_address"] == eth_address
        assert event["args"]["endpoint"] == endpoint

    return get


def check_channel_opened(
    channel_identifier: int, participant1: Address, participant2: Address, settle_timeout: int
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["participant1"] == participant1
        assert event["args"]["participant2"] == participant2
        assert event["args"]["settle_timeout"] == settle_timeout

    return get


# Check TokenNetwork.ChannelNewDeposit events. Not for UDC deposits!
def check_new_deposit(
    channel_identifier: int, participant: Address, deposit: int
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["participant"] == participant
        assert event["args"]["total_deposit"] == deposit

    return get


def check_withdraw(
    channel_identifier: int, participant: Address, withdrawn_amount: int
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["participant"] == participant
        assert event["args"]["total_withdraw"] == withdrawn_amount

    return get


def check_channel_closed(
    channel_identifier: int, closing_participant: Address, nonce: int
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["closing_participant"] == closing_participant
        assert event["args"]["nonce"] == nonce

    return get


def check_channel_unlocked(
    channel_identifier: int,
    participant: Address,
    partner: Address,
    locksroot: bytes,
    unlocked_amount: int,
    returned_tokens: int,
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["participant"] == participant
        assert event["args"]["partner"] == partner
        assert event["args"]["locksroot"] == locksroot
        assert event["args"]["unlocked_amount"] == unlocked_amount
        assert event["args"]["returned_tokens"] == returned_tokens

    return get


def check_transfer_updated(
    channel_identifier: int, closing_participant: Address, nonce: int
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["closing_participant"] == closing_participant
        assert event["args"]["nonce"] == nonce

    return get


def check_channel_settled(
    channel_identifier: int, participant1_amount: int, participant2_amount: int
) -> Callable[[Dict[str, Any]], None]:
    def get(event: Dict[str, Any]) -> None:
        assert event["args"]["channel_identifier"] == channel_identifier
        assert event["args"]["participant1_amount"] == participant1_amount
        assert event["args"]["participant2_amount"] == participant2_amount

    return get
