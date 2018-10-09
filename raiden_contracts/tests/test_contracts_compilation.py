import pytest
from pathlib import Path

from raiden_contracts.contract_manager import (
    ContractManager,
    CONTRACTS_SOURCE_DIRS,
    CONTRACTS_PRECOMPILED_PATH,
    ContractManagerVerificationError,
)
from raiden_contracts.constants import (
    CONTRACTS_VERSION,
    CONTRACT_TOKEN_NETWORK,
    ChannelEvent,
)


def test_verification_overall_checksum():
    manager = ContractManager(CONTRACTS_SOURCE_DIRS)
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

    original_checksum = manager.overall_checksum

    # We change the source code overall checksum
    manager.overall_checksum += '2'
    # Now the verification should fail
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

    manager.overall_checksum = None
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

    manager.overall_checksum = ''
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

    checksum_fail = list(original_checksum)
    # Replace the first char with a different one
    checksum_fail[0] = list(filter(lambda x: x != checksum_fail[0], ['2', 'a']))[0]
    manager.overall_checksum = "".join(checksum_fail)
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

    manager.overall_checksum = original_checksum
    manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)


def test_verification_contracts_checksums():
    manager = ContractManager(CONTRACTS_SOURCE_DIRS)
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

    for contract, checksum in manager.contracts_checksums.items():
        manager.contracts_checksums[contract] += '2'
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

        manager.contracts_checksums[contract] = None
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

        manager.contracts_checksums[contract] = ''
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

        checksum_fail = list(checksum)
        # Replace the first char with a different one
        checksum_fail[0] = list(filter(lambda x: x != checksum_fail[0], ['2', 'a']))[0]
        manager.contracts_checksums[contract] = "".join(checksum_fail)
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)

        manager.contracts_checksums[contract] = checksum
        manager.verify_precompiled_checksums(CONTRACTS_PRECOMPILED_PATH)


def test_contracts_version():
    manager = ContractManager(CONTRACTS_PRECOMPILED_PATH)
    assert manager.contracts_version == CONTRACTS_VERSION


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
    ContractManager(CONTRACTS_SOURCE_DIRS).compile_contracts(precompiled_path)
    # try to load contracts from a precompiled file
    contract_manager_meta(precompiled_path)
