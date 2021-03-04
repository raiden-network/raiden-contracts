from eth_typing import HexAddress
from eth_utils import encode_hex, keccak


def get_solidity_key_for_library_identifier(library_identifier: str) -> str:
    return encode_hex(keccak(bytes(library_identifier, "utf-8")))[2:36]


def get_placeholder_for_library_identifier(library_identifier: str) -> str:
    solidity_key = get_solidity_key_for_library_identifier(library_identifier)
    return f"__${solidity_key}$__"


def link_bytecode(
    unlinked_bytecode: str, library_identifier: str, library_address: HexAddress
) -> str:
    """Links compiled bytecode by replacing the hashed library identifer
    with the libraries address."""

    normalized_address = library_address[2:].lower()
    return unlinked_bytecode.replace(
        get_placeholder_for_library_identifier(library_identifier),
        normalized_address,
    )
