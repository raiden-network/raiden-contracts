from eth_typing import HexAddress, HexStr

from raiden_contracts.constants import LIBRARY_TOKEN_NETWORK_UTILS_LINK_KEY
from raiden_contracts.utils.linking import get_placeholder_for_library_identifier, link_bytecode


def test_solidity_placeholder_calculation() -> None:
    assert (
        get_placeholder_for_library_identifier(LIBRARY_TOKEN_NETWORK_UTILS_LINK_KEY)
        == "__$34600480520cb524a2c423e33a5b4dd437$__"
    )


def test_linking() -> None:
    unlinked_bytecode = "73__$34600480520cb524a2c423e33a5b4dd437$__63"
    lib_address = HexAddress(HexStr("0x1111111111111111111111111111111111111111"))
    linked_bytecode = link_bytecode(
        unlinked_bytecode, LIBRARY_TOKEN_NETWORK_UTILS_LINK_KEY, lib_address
    )

    assert linked_bytecode == "73111111111111111111111111111111111111111163"
