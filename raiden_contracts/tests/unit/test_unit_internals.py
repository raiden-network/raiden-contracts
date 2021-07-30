from itertools import chain, product

import pytest
from eth_tester.constants import UINT256_MAX, UINT256_MIN
from web3.contract import Contract
from web3.exceptions import ValidationError

from raiden_contracts.contract_source_manager import check_runtime_codesize


def test_min_uses_usigned(token_network: Contract) -> None:
    """Min cannot be called with negative values"""
    INVALID_VALUES = [-UINT256_MAX, -1]
    VALID_VALUES = [UINT256_MIN, UINT256_MAX, UINT256_MAX]

    all_invalid = chain(
        product(VALID_VALUES, INVALID_VALUES), product(INVALID_VALUES, VALID_VALUES)
    )

    for a, b in all_invalid:
        with pytest.raises(ValidationError):
            token_network.functions.min(a, b).call()


def test_min(token_network: Contract) -> None:
    """Min works like Python's min"""
    VALUES = [UINT256_MIN, 1, UINT256_MAX, UINT256_MAX]
    for a, b in product(VALUES, VALUES):
        assert token_network.functions.min(a, b).call() == min(a, b)


def test_too_big_runtime_code() -> None:
    compilation = {"TestContract": {"bin-runtime": "33" * 0x6001}}
    with pytest.raises(RuntimeError):
        check_runtime_codesize(compilation)
