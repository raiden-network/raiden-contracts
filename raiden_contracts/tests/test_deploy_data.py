from typing import Optional

import pytest

from raiden_contracts.constants import CONTRACTS_VERSION, DeploymentModule
from raiden_contracts.contract_manager import (
    contracts_data_path,
    contracts_deployed_path,
    get_contracts_deployed,
    get_contracts_deployment_info,
    merge_deployment_data,
    version_provides_services,
)


@pytest.mark.parametrize('version', [None, CONTRACTS_VERSION])
def test_deploy_data_dir_exists(version: Optional[str]):
    """ Make sure directories exist for deployment data """
    assert contracts_data_path(version).exists(), 'deployment data do not exist'
    assert contracts_data_path(version).is_dir()


@pytest.mark.parametrize('version', [None, CONTRACTS_VERSION])
def test_deploy_data_dir_is_not_nested(version: Optional[str]):
    """ Make sure 'data' directories do not contain 'data*' recursively """
    assert list(contracts_data_path(version).glob('./data*')) == []


@pytest.mark.parametrize('version', [None, CONTRACTS_VERSION])
@pytest.mark.parametrize('chain_id', [3, 4, 42])
@pytest.mark.parametrize('services', [False, True])
def test_deploy_data_file_exists(
        version: Optional[str],
        chain_id: int,
        services: bool,
):
    """ Make sure files exist for deployment data of each chain_id """
    assert contracts_deployed_path(chain_id, version, services).exists()


def reasonable_deployment_of_a_contract(deployed):
    """ Checks an entry under deployment_*.json under a contract name """
    assert isinstance(deployed['address'], str)
    assert len(deployed['address']) == 42
    assert isinstance(deployed['transaction_hash'], str)
    assert len(deployed['transaction_hash']) == 66
    assert isinstance(deployed['block_number'], int)
    assert deployed['block_number'] > 0
    assert isinstance(deployed['gas_cost'], int)
    assert deployed['gas_cost'] > 0
    assert isinstance(deployed['constructor_arguments'], list)


RAIDEN_CONTRACT_NAMES = ('EndpointRegistry', 'TokenNetworkRegistry', 'SecretRegistry')


@pytest.mark.parametrize('version', [None])
@pytest.mark.parametrize('chain_id', [3, 4, 42])
def test_deploy_data_has_fields_raiden(
        version: Optional[str],
        chain_id: int,
):
    data = get_contracts_deployed(chain_id, version, services=False)
    data2 = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.RAIDEN)
    assert data2 == data
    assert data['contracts_version'] == version if version else CONTRACTS_VERSION
    assert data['chain_id'] == chain_id
    contracts = data['contracts']
    for name in RAIDEN_CONTRACT_NAMES:
        deployed = contracts[name]
        reasonable_deployment_of_a_contract(deployed)


SERVICE_CONTRACT_NAMES = ('ServiceRegistry', 'MonitoringService', 'OneToN', 'UserDeposit')


@pytest.mark.parametrize('version', [None])
@pytest.mark.parametrize('chain_id', [3, 4, 42])
def test_deploy_data_has_fields_services(
        version: Optional[str],
        chain_id: int,
):
    data = get_contracts_deployed(chain_id, version, services=True)
    data2 = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.SERVICES)
    assert data2 == data
    assert data['contracts_version'] == version if version else CONTRACTS_VERSION
    assert data['chain_id'] == chain_id
    contracts = data['contracts']
    for name in SERVICE_CONTRACT_NAMES:
        deployed = contracts[name]
        reasonable_deployment_of_a_contract(deployed)


@pytest.mark.parametrize('version', [None])
@pytest.mark.parametrize('chain_id', [3, 4, 42])
def test_deploy_data_all(
        version: Optional[str],
        chain_id: int,
):
    data_services = get_contracts_deployed(chain_id, version, services=True)
    data_raiden = get_contracts_deployed(chain_id, version, services=False)
    data_all_computed = merge_deployment_data(data_services, data_raiden)
    data_all = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.ALL)
    data_default = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.ALL)
    assert data_all == data_all_computed
    assert data_all == data_default

    for name in RAIDEN_CONTRACT_NAMES + SERVICE_CONTRACT_NAMES:
        deployed = data_all['contracts'][name]
        reasonable_deployment_of_a_contract(deployed)


def test_deploy_data_unknown_module():
    with pytest.raises(ValueError):
        get_contracts_deployment_info(3, None, module=None)  # type: ignore


@pytest.mark.parametrize('chain_id', [3, 4, 42])
def test_deploy_data_for_redeyes_succeed(chain_id):
    """ get_contracts_deployment_info() on RedEyes version should return a non-empty dictionary """
    assert get_contracts_deployment_info(chain_id, '0.4.0')


@pytest.mark.parametrize('chain_id', [3, 4, 42])
def test_service_deploy_data_for_redeyes_fail(chain_id):
    """ get_contracts_deployment_info() on RedEyes version should return a non-empty dictionary """
    with pytest.raises(ValueError):
        assert get_contracts_deployment_info(chain_id, '0.4.0', DeploymentModule.SERVICES)


def test_version_provides_services():
    assert not version_provides_services('0.3._')
    assert not version_provides_services('0.4.0')
    assert version_provides_services('0.8.0')
    assert version_provides_services('0.8.0_unlimited')
    assert version_provides_services('0.10.1')
    assert version_provides_services('0.11.0')
    with pytest.raises(ValueError):
        assert version_provides_services('not a semver')
