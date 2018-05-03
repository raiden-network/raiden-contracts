from raiden_contracts.contract_manager import (
    ContractManager,
    CONTRACTS_SOURCE_DIRS,
)
import pytest

PRECOMPILED_CONTRACTS_PATH = 'raiden_contracts/data/contracts.json'


def contract_manager_meta(contracts_path):
    manager = ContractManager(contracts_path)

    abi = manager.get_contract_abi('TokenNetwork')
    assert isinstance(abi, list)
    with pytest.raises(KeyError):
        manager.get_contract_abi('SomeName')

    abi = manager.get_event_abi('TokenNetwork', 'ChannelClosed')
    assert isinstance(abi, dict)
    with pytest.raises(KeyError):
        manager.get_event_abi('TokenNetwork', 'NonExistant')


def test_contract_manager_compile():
    contract_manager_meta(CONTRACTS_SOURCE_DIRS)


def test_contract_manager_json():
    # try to load contracts from a precompiled file
    contract_manager_meta(PRECOMPILED_CONTRACTS_PATH)
