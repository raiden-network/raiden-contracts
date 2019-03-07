from typing import Optional

import pytest

from raiden_contracts.constants import CONTRACTS_VERSION
from raiden_contracts.contract_manager import (
    contracts_data_path,
    contracts_deployed_path,
    get_contracts_deployed,
)


@pytest.mark.parametrize("version", [None, CONTRACTS_VERSION])
def test_deploy_data_dir_exists(version: Optional[str]):
    """ Make sure directories exist for deployment data """
    assert contracts_data_path(version).exists(), "deployment data do not exist"
    assert contracts_data_path(version).is_dir()


@pytest.mark.parametrize('version', [None, CONTRACTS_VERSION])
def test_deploy_data_dir_is_not_nested(version: Optional[str]):
    """ Make sure 'data' directories do not contain 'data*' recursively """
    assert list(contracts_data_path(version).glob('./data*')) == []


@pytest.mark.parametrize("version", [None, CONTRACTS_VERSION])
@pytest.mark.parametrize("chain_id", [3, 4, 42])
@pytest.mark.parametrize("services", [False, True])
def test_deploy_data_file_exists(
        version: Optional[str],
        chain_id: int,
        services: bool,
):
    """ Make sure files exist for deployment data of each chain_id """
    assert contracts_deployed_path(chain_id, version, services).exists()


def reasonable_deployment_of_a_contract(deployed):
    """ Checks an entry under deployment_*.json under a contract name """
    assert isinstance(deployed["address"], str)
    assert len(deployed["address"]) == 42
    assert isinstance(deployed["transaction_hash"], str)
    assert len(deployed["transaction_hash"]) == 66
    assert isinstance(deployed["block_number"], int)
    assert deployed["block_number"] > 0
    assert isinstance(deployed["gas_cost"], int)
    assert deployed["gas_cost"] > 0
    assert isinstance(deployed["constructor_arguments"], list)


@pytest.mark.parametrize("version", [None])
@pytest.mark.parametrize("chain_id", [3, 4, 42])
def test_deploy_data_has_fields_raiden(
        version: Optional[str],
        chain_id: int,
):
    data = get_contracts_deployed(chain_id, version, services=False)
    assert data["contracts_version"] == version if version else CONTRACTS_VERSION
    assert data["chain_id"] == chain_id
    contracts = data["contracts"]
    for name in {"EndpointRegistry", "TokenNetworkRegistry", "SecretRegistry"}:
        deployed = contracts[name]
        reasonable_deployment_of_a_contract(deployed)


@pytest.mark.parametrize("version", [None])
@pytest.mark.parametrize("chain_id", [3, 4, 42])
def test_deploy_data_has_fields_services(
        version: Optional[str],
        chain_id: int,
):
    data = get_contracts_deployed(chain_id, version, services=True)
    assert data["contracts_version"] == version if version else CONTRACTS_VERSION
    assert data["chain_id"] == chain_id
    contracts = data["contracts"]
    for name in {"ServiceRegistry", "MonitoringService", "OneToN", "UserDeposit"}:
        deployed = contracts[name]
        reasonable_deployment_of_a_contract(deployed)
