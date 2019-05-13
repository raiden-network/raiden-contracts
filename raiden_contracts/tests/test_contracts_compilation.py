from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    CONTRACTS_VERSION,
    NETWORKNAME_TO_ID,
    PRECOMPILED_DATA_FIELDS,
    ChannelEvent,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    ContractManagerLoadError,
    contract_version_string,
    contracts_deployed_path,
    contracts_precompiled_path,
)
from raiden_contracts.contract_source_manager import (
    ContractSourceManager,
    ContractSourceManagerVerificationError,
    contracts_source_path,
)


def check_precompiled_content(manager, contract_names, fields):
    for contract_name in contract_names:
        for field in fields:
            assert manager.contracts[contract_name][field]


def test_nonexistent_precompiled_path():
    """ An exception occurs when trying to access a field in a non-existent precompiled path """
    nonexistent_version = "0.6.0"
    with pytest.raises(FileNotFoundError):
        ContractManager(contracts_precompiled_path(nonexistent_version))


def test_verification_without_checksum():
    """ Call ContractSourceManager.verify_precompiled_checksums() before computing the checksum """
    manager = ContractSourceManager(contracts_source_path())
    with pytest.raises(AttributeError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())


def test_verification_overall_checksum():
    """ Tamper with the overall checksum and see failures in verify_precompiled_checksums() """
    manager = ContractSourceManager(contracts_source_path())
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(contracts_precompiled_path())

    assert manager.overall_checksum
    original_checksum = manager.overall_checksum

    # We change the source code overall checksum
    manager.overall_checksum += "2"
    # Now the verification should fail
    with pytest.raises(ContractSourceManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    manager.overall_checksum = None  # type: ignore
    with pytest.raises(ContractSourceManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    manager.overall_checksum = ""
    with pytest.raises(ContractSourceManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    checksum_fail = list(original_checksum)
    # Replace the first char with a different one
    checksum_fail[0] = "a" if checksum_fail[0] == "2" else "2"
    manager.overall_checksum = "".join(checksum_fail)
    with pytest.raises(ContractSourceManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path())

    manager.overall_checksum = original_checksum
    manager.verify_precompiled_checksums(contracts_precompiled_path())


def test_verification_contracts_checksums():
    """ Tamper with the contract checksums and see failures in verify_precompiled_checksums() """
    manager = ContractSourceManager(contracts_source_path())
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(contracts_precompiled_path())

    assert manager.contracts_checksums
    for contract, checksum in manager.contracts_checksums.items():
        manager.contracts_checksums[contract] += "2"
        with pytest.raises(ContractSourceManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        manager.contracts_checksums[contract] = None  # type: ignore
        with pytest.raises(ContractSourceManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        manager.contracts_checksums[contract] = ""
        with pytest.raises(ContractSourceManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        checksum_fail = list(checksum)
        # Replace the first char with a different one
        checksum_fail[0] = "a" if checksum_fail[0] == "2" else "2"
        manager.contracts_checksums[contract] = "".join(checksum_fail)
        with pytest.raises(ContractSourceManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path())

        manager.contracts_checksums[contract] = checksum
        manager.verify_precompiled_checksums(contracts_precompiled_path())


def test_current_development_version():
    """ contracts_source_path() exists and contains the expected files """
    contracts_version = CONTRACTS_VERSION
    contract_names = [
        "Utils",
        "EndpointRegistry",
        "SecretRegistry",
        "TokenNetworkRegistry",
        "TokenNetwork",
        "MonitoringService",
        "ServiceRegistry",
    ]

    manager = ContractManager(contracts_precompiled_path(contracts_version))
    assert manager.contracts_version == contracts_version
    check_precompiled_content(manager, contract_names, PRECOMPILED_DATA_FIELDS)

    for _, source_path in contracts_source_path().items():
        assert source_path.exists()
    assert contracts_precompiled_path().exists()

    # deployment files exist
    assert contracts_deployed_path(NETWORKNAME_TO_ID["rinkeby"]).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["ropsten"]).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["kovan"]).exists()
    # deployment files for service contracts also exist
    assert contracts_deployed_path(NETWORKNAME_TO_ID["rinkeby"], services=True).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["ropsten"], services=True).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["kovan"], services=True).exists()


def test_red_eyes_version():
    """ contracts_source_path('0.4.0') exists and contains the expected files """
    contracts_version = "0.4.0"
    contract_names = [
        "Utils",
        "EndpointRegistry",
        "SecretRegistry",
        "TokenNetworkRegistry",
        "TokenNetwork",
    ]

    manager = ContractManager(contracts_precompiled_path(contracts_version))
    assert manager.contracts_version == contracts_version
    check_precompiled_content(manager, contract_names, PRECOMPILED_DATA_FIELDS)

    assert contracts_precompiled_path(contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["mainnet"], contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["rinkeby"], contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["ropsten"], contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["kovan"], contracts_version).exists()


def test_pre_limits_version():
    """ contracts_source_path('0.3._') exists and contains the expected files """
    contracts_version = "0.3._"
    contract_names = [
        "Utils",
        "EndpointRegistry",
        "SecretRegistry",
        "TokenNetworkRegistry",
        "TokenNetwork",
    ]

    manager = ContractManager(contracts_precompiled_path(contracts_version))
    assert manager.contracts_version == contracts_version
    check_precompiled_content(manager, contract_names, PRECOMPILED_DATA_FIELDS)

    assert contracts_precompiled_path(contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["rinkeby"], contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["ropsten"], contracts_version).exists()
    assert contracts_deployed_path(NETWORKNAME_TO_ID["kovan"], contracts_version).exists()


def contract_manager_meta(contracts_path, source: bool):
    """ See failures in looking up non-existent ABI entries of TokenNetwork and CLOSED """
    with NamedTemporaryFile() as tmpfile:
        if source:
            manager = ContractSourceManager(contracts_path).compile_contracts(Path(tmpfile.name))
        else:
            manager = ContractManager(contracts_path)

        abi = manager.get_contract_abi(CONTRACT_TOKEN_NETWORK)
        assert isinstance(abi, list)
        with pytest.raises(KeyError):
            manager.get_contract_abi("SomeName")
        with pytest.raises(KeyError):
            manager.get_contract("SomeName")

        abi2 = manager.get_event_abi(CONTRACT_TOKEN_NETWORK, ChannelEvent.CLOSED)
        assert isinstance(abi2, dict)
        with pytest.raises(ValueError):
            manager.get_event_abi(CONTRACT_TOKEN_NETWORK, "NonExistant")


def test_contract_manager_compile():
    """ Check the ABI in the sources """
    contract_manager_meta(contracts_source_path(), source=True)


def test_contract_manager_json(tmpdir):
    """ Check the ABI in contracts.json """
    precompiled_path = Path(str(tmpdir)).joinpath("contracts.json")
    ContractSourceManager(contracts_source_path()).compile_contracts(precompiled_path)
    # try to load contracts from a precompiled file
    contract_manager_meta(precompiled_path, source=False)


def test_contract_manager_constructor_does_not_invent_version():
    """ ContractManager should not invent a version string """
    manager = ContractManager(contracts_precompiled_path(version=None))
    assert manager.contracts_version is None


@pytest.mark.parametrize("version", [CONTRACTS_VERSION, "0.9.0", "0.3._", "0.4.0"])
def test_contract_manager_constructor_keeps_existing_versions(version):
    """ ContractManager should keep an existing version string """
    manager = ContractManager(contracts_precompiled_path(version=version))
    assert manager.contracts_version == version


def test_contract_manager_precompiled_load_error():
    """ ContractManager's constructor raises ContractManagerLoadError when precompiled
    contracts cannot be loaded """
    with NamedTemporaryFile() as empty_file:
        with pytest.raises(ContractManagerLoadError):
            ContractManager(Path(empty_file.name))


def test_contract_source_manager_constructor_with_wrong_type():
    """ ConstructSourceManager's constructor raises TypeError on a wrong kind of argument """
    with pytest.raises(TypeError):
        ContractSourceManager(None)  # type: ignore


def test_contract_version_string_with_none():
    assert contract_version_string(version=None) == CONTRACTS_VERSION
