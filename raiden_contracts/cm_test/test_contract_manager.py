from pathlib import Path

import pytest

from raiden_contracts.contract_manager import (
    ContractManager,
    CONTRACTS_SOURCE_DIRS,
)
from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    ChannelEvent,
)


def contract_manager_meta(contracts_path):
    manager = ContractManager(contracts_path)

    abi = manager.get_contract_abi(CONTRACT_TOKEN_NETWORK)
    assert isinstance(abi, list)
    with pytest.raises(KeyError):
        manager.get_contract_abi('SomeName')

    abi = manager.get_event_abi(CONTRACT_TOKEN_NETWORK, ChannelEvent.CLOSED)
    assert isinstance(abi, dict)
    with pytest.raises(ValueError):
        manager.get_event_abi(CONTRACT_TOKEN_NETWORK, 'NonExistant')


def test_contract_manager_compile():
    contract_manager_meta(CONTRACTS_SOURCE_DIRS)


def test_contract_manager_json(tmpdir):
    precompiled_path = Path(str(tmpdir)).joinpath('contracts.json')
    ContractManager(CONTRACTS_SOURCE_DIRS).store_compiled_contracts(precompiled_path)
    # try to load contracts from a precompiled file
    contract_manager_meta(precompiled_path)
