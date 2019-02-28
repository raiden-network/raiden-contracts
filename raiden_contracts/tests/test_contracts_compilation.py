import pytest
from pathlib import Path

from raiden_contracts.contract_manager import (
    ContractManager,
    contracts_source_path,
    contracts_precompiled_path,
    contracts_deployed_path,
    ContractManagerVerificationError,
    Flavor,
)
from raiden_contracts.constants import (
    CONTRACTS_VERSION,
    PRECOMPILED_DATA_FIELDS,
    CONTRACT_TOKEN_NETWORK,
    NETWORKNAME_TO_ID,
    PlainVersion,
    ChannelEvent,
)


def check_precompiled_content(manager, contract_names, fields):
    for contract_name in contract_names:
        for field in fields:
            assert manager.contracts[contract_name][field]


def test_nonexistent_precompiled_path():
    """ An exception occurs when trying to access a field in a non-existent precompiled path """
    nonexistent_version = PlainVersion('0.6.0')
    with pytest.raises(FileNotFoundError):
        ContractManager(flavor=Flavor.Limited, path=contracts_precompiled_path(
            Flavor.Limited,
            nonexistent_version,
        ))


def test_verification_overall_checksum():
    """ Tamper with the overall checksum and see failures in verify_precompiled_checksums() """
    manager = ContractManager(flavor=Flavor.Limited, path=contracts_source_path(Flavor.Limited))
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

    assert manager.overall_checksum
    original_checksum = manager.overall_checksum

    # We change the source code overall checksum
    manager.overall_checksum += '2'
    # Now the verification should fail
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

    manager.overall_checksum = None
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

    manager.overall_checksum = ''
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

    checksum_fail = list(original_checksum)
    # Replace the first char with a different one
    checksum_fail[0] = list(filter(lambda x: x != checksum_fail[0], ['2', 'a']))[0]
    manager.overall_checksum = "".join(checksum_fail)
    with pytest.raises(ContractManagerVerificationError):
        manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

    manager.overall_checksum = original_checksum
    manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))


def test_verification_contracts_checksums():
    """ Tamper with the contract checksums and see failures in verify_precompiled_checksums() """
    manager = ContractManager(flavor=Flavor.Limited, path=contracts_source_path(Flavor.Limited))
    manager.checksum_contracts()
    manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

    assert manager.contracts_checksums
    for contract, checksum in manager.contracts_checksums.items():
        manager.contracts_checksums[contract] += '2'
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

        manager.contracts_checksums[contract] = None  # type: ignore
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

        manager.contracts_checksums[contract] = ''
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

        checksum_fail = list(checksum)
        # Replace the first char with a different one
        checksum_fail[0] = list(filter(lambda x: x != checksum_fail[0], ['2', 'a']))[0]
        manager.contracts_checksums[contract] = "".join(checksum_fail)
        with pytest.raises(ContractManagerVerificationError):
            manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))

        manager.contracts_checksums[contract] = checksum
        manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))


def test_contracts_version():
    """ Check the value of contracts_version """
    manager = ContractManager(
        flavor=Flavor.Limited,
        path=contracts_precompiled_path(Flavor.Limited),
    )
    assert manager.contracts_version == CONTRACTS_VERSION


def test_current_development_version():
    """ contracts_source_path() exists and contains the expected files """
    contracts_version = CONTRACTS_VERSION
    contract_names = [
        'Utils',
        'EndpointRegistry',
        'SecretRegistry',
        'TokenNetworkRegistry',
        'TokenNetwork',
        'MonitoringService',
        'ServiceRegistry',
    ]

    manager = ContractManager(
        flavor=Flavor.Limited,
        path=contracts_precompiled_path(Flavor.Limited, contracts_version),
    )
    assert manager.contracts_version == contracts_version
    check_precompiled_content(manager, contract_names, PRECOMPILED_DATA_FIELDS)

    for _, source_path in contracts_source_path(Flavor.Limited).items():
        assert source_path.exists()
    assert contracts_precompiled_path(Flavor.Limited).exists()

    for flavor in {Flavor.Limited}:  # TODO: addd Flavor.Unlimited when ready
        # deployment files exist
        assert contracts_deployed_path(NETWORKNAME_TO_ID['rinkeby'], flavor).exists()
        assert contracts_deployed_path(NETWORKNAME_TO_ID['ropsten'], flavor).exists()
        assert contracts_deployed_path(NETWORKNAME_TO_ID['kovan'], flavor).exists()
        # deployment files for service contracts also exist
        assert contracts_deployed_path(
            NETWORKNAME_TO_ID['rinkeby'],
            flavor,
            services=True,
        ).exists()
        assert contracts_deployed_path(
            NETWORKNAME_TO_ID['ropsten'],
            flavor,
            services=True,
        ).exists()
        assert contracts_deployed_path(
            NETWORKNAME_TO_ID['kovan'],
            flavor,
            services=True,
        ).exists()


def test_red_eyes_version():
    """ contracts_source_path('0.4.0') exists and contains the expected files """
    contracts_version = PlainVersion('0.4.0')
    contract_names = [
        'Utils',
        'EndpointRegistry',
        'SecretRegistry',
        'TokenNetworkRegistry',
        'TokenNetwork',
    ]

    manager = ContractManager(
        flavor=Flavor.Limited,
        path=contracts_precompiled_path(Flavor.Limited, contracts_version),
    )
    assert manager.contracts_version == contracts_version
    check_precompiled_content(manager, contract_names, PRECOMPILED_DATA_FIELDS)

    assert contracts_precompiled_path(Flavor.Limited, contracts_version).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['mainnet'],
        Flavor.Limited,
        contracts_version,
    ).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['rinkeby'],
        Flavor.Limited,
        contracts_version,
    ).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['ropsten'],
        Flavor.Limited,
        contracts_version,
    ).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['kovan'],
        Flavor.Limited,
        contracts_version,
    ).exists()


def test_pre_limits_version():
    """ contracts_source_path('0.3._') exists and contains the expected files """
    contracts_version = PlainVersion('0.3._')
    contract_names = [
        'Utils',
        'EndpointRegistry',
        'SecretRegistry',
        'TokenNetworkRegistry',
        'TokenNetwork',
    ]

    manager = ContractManager(
        flavor=Flavor.Limited,
        path=contracts_precompiled_path(Flavor.Limited, contracts_version),
    )
    assert manager.contracts_version == contracts_version
    check_precompiled_content(manager, contract_names, PRECOMPILED_DATA_FIELDS)

    assert contracts_precompiled_path(Flavor.Limited, contracts_version).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['rinkeby'],
        Flavor.Limited,
        contracts_version,
    ).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['ropsten'],
        Flavor.Limited,
        contracts_version,
    ).exists()
    assert contracts_deployed_path(
        NETWORKNAME_TO_ID['kovan'],
        Flavor.Limited,
        contracts_version,
    ).exists()


def contract_manager_meta(contracts_path):
    """ See failures in looking up non-existent ABI entries of TokenNetwork and CLOSED """
    manager = ContractManager(flavor=Flavor.Limited, path=contracts_path)

    abi = manager.get_contract_abi(CONTRACT_TOKEN_NETWORK)
    assert isinstance(abi, list)
    with pytest.raises(KeyError):
        manager.get_contract_abi('SomeName')

    abi = manager.get_event_abi(CONTRACT_TOKEN_NETWORK, ChannelEvent.CLOSED)
    assert isinstance(abi, dict)
    with pytest.raises(ValueError):
        manager.get_event_abi(CONTRACT_TOKEN_NETWORK, 'NonExistant')


def test_contract_manager_compile():
    """ Check the ABI in the sources """
    contract_manager_meta(contracts_source_path(Flavor.Limited))


def test_contract_manager_json(tmpdir):
    """ Check the ABI in contracts.json """
    precompiled_path = Path(str(tmpdir)).joinpath('contracts.json')
    ContractManager(
        flavor=Flavor.Limited,
        path=contracts_source_path(Flavor.Limited),
    ).compile_contracts(precompiled_path)
    # try to load contracts from a precompiled file
    contract_manager_meta(precompiled_path)
