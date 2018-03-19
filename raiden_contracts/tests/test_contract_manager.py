from raiden_contracts.contract_manager import ContractManager, CONTRACTS_SOURCE_DIRS
import pytest

PRECOMPILED_CONTRACTS_PATH = 'raiden_contracts/data/contracts.json'


def contract_manager_meta(contracts_path):
    manager = ContractManager(contracts_path)
    abi = manager.get_contract_abi('TokenNetwork')
    assert isinstance(abi, list)
    abi = manager.get_event_abi('TokenNetwork', 'ChannelClosed')
    assert isinstance(abi, dict)


def test_contract_manager_compile():
    # try to load & compile contracts from a source directory
    contract_manager_meta(CONTRACTS_SOURCE_DIRS)


def test_contract_manager_json():
    # try to load contracts from a precompiled file
    contract_manager_meta(PRECOMPILED_CONTRACTS_PATH)


def test_solc_unavailable():
    # test scenario where solc is unavailable
    import raiden_contracts
    from ethereum.tools import _solidity
    _solidity.get_compiler_path = lambda: None
    import importlib
    importlib.reload(raiden_contracts.contract_manager)
    with pytest.raises(_solidity.CompileError):
        contract_manager_meta(CONTRACTS_SOURCE_DIRS)
