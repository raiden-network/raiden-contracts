from itertools import chain, product

import pytest
from eth_tester.constants import UINT256_MIN, UINT256_MAX
from web3.exceptions import ValidationError


def test_min_uses_usigned(token_network_utils_library):
    """ Min cannot be called with negative values. """
    INVALID_VALUES = [-UINT256_MAX, -1]
    VALID_VALUES = [UINT256_MIN, UINT256_MAX, UINT256_MAX]

    all_invalid = chain(
        product(VALID_VALUES, INVALID_VALUES),
        product(INVALID_VALUES, VALID_VALUES),
    )

    for a, b in all_invalid:
        with pytest.raises(ValidationError):
            token_network_utils_library.functions.min(a, b).call()


def test_min(token_network_utils_library):

    VALUES = [UINT256_MIN, 1, UINT256_MAX, UINT256_MAX]
    for a, b in product(VALUES, VALUES):
        assert token_network_utils_library.functions.min(a, b).call() == min(a, b)
