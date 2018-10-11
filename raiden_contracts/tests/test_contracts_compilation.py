import pytest
from pathlib import Path

from raiden_contracts.contract_manager import (
    ContractManager,
    contracts_source_path,
    contracts_precompiled_path,
    contracts_deployed_path,
    ContractManagerVerificationError,
)
from raiden_contracts.constants import (
    CONTRACTS_VERSION,
    CONTRACT_TOKEN_NETWORK,
    NETWORKNAME_TO_ID,
    ChannelEvent,
)


def test_verification_overall_checksum():
    manager = ContractManager(contracts_source_path())
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(contracts_precompiled_path())

    original_checksum = manager.overall_checksum

    # We change the source code overall checksum
    manager.overall_checksum += '2'
    # Now the verification should fail
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    manager.overall_checksum = None
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    manager.overall_checksum = ''
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    checksum_fail = list(original_checksum)
    # Replace the first char with a different one
    checksum_fail[0] = list(filter(lambda x: x != checksum_fail[0], ['2', 'a']))[0]
    manager.overall_checksum = "".join(checksum_fail)
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    manager.overall_checksum = original_checksum
    manager.verify_precompiled_checksums(contracts_precompiled_path())


def test_verification_contracts_checksums():
    manager = ContractManager(contracts_source_path())
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(contracts_precompiled_path())

    for contract, checksum in manager.contracts_checksums.items():
        manager.contracts_checksums[contract] += '2'
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        manager.contracts_checksums[contract] = None
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        manager.contracts_checksums[contract] = ''
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        checksum_fail = list(checksum)
        # Replace the first char with a different one
        checksum_fail[0] = list(filter(lambda x: x != checksum_fail[0], ['2', 'a']))[0]
        manager.contracts_checksums[contract] = "".join(checksum_fail)
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        manager.contracts_checksums[contract] = checksum
        manager.verify_precompiled_checksums(contracts_precompiled_path())


def test_contracts_version():
    manager = ContractManager(contracts_precompiled_path())
    assert manager.contracts_version == CONTRACTS_VERSION


def test_paths():
    for _, source_path in contracts_source_path().items():
        assert source_path.exists()
    assert contracts_precompiled_path().exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID['rinkeby']).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID['ropsten']).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID['kovan']).exists()


def test_pre_limits_version():
    manager = ContractManager(contracts_precompiled_path('pre_limits'))
    assert manager.contracts_version == '0.3._'
    assert contracts_precompiled_path('pre_limits').exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID['rinkeby'], 'pre_limits').exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID['ropsten'], 'pre_limits').exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID['kovan'], 'pre_limits').exists()


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
    contract_manager_meta(contracts_source_path())


def test_contract_manager_json(tmpdir):
    precompiled_path = Path(str(tmpdir)).joinpath('contracts.json')
    ContractManager(contracts_source_path()).compile_contracts(precompiled_path)
    # try to load contracts from a precompiled file
    contract_manager_meta(precompiled_path)
