from typing import Optional
from unittest.mock import Mock

import pytest
from eth_typing import HexAddress, HexStr
from web3.contract import Contract

from raiden_contracts.constants import (
    ALDERAAN_VERSION,
    CONTRACTS_VERSION,
    EMPTY_ADDRESS,
    DeploymentModule,
)
from raiden_contracts.contract_manager import (
    DeployedContract,
    contracts_data_path,
    contracts_deployed_path,
    get_contracts_deployment_info,
)
from raiden_contracts.deploy.contract_verifier import ContractVerifier
from raiden_contracts.utils.type_aliases import ChainID
from raiden_contracts.utils.versions import contracts_version_provides_services


@pytest.mark.parametrize("version", [None, CONTRACTS_VERSION])
def test_deploy_data_dir_exists(version: Optional[str]) -> None:
    """Make sure directories exist for deployment data"""
    assert contracts_data_path(version).exists(), "deployment data do not exist"
    assert contracts_data_path(version).is_dir()


@pytest.mark.parametrize("version", [None, CONTRACTS_VERSION])
def test_deploy_data_dir_is_not_nested(version: Optional[str]) -> None:
    """Make sure 'data' directories do not contain 'data*' recursively"""
    assert list(contracts_data_path(version).glob("./data*")) == []


@pytest.mark.parametrize("version", [None, CONTRACTS_VERSION])
@pytest.mark.parametrize("chain_id", [3, 4, 5])
@pytest.mark.parametrize("services", [False, True])
def test_deploy_data_file_exists(
    version: Optional[str], chain_id: ChainID, services: bool
) -> None:
    """Make sure files exist for deployment data of each chain_id"""
    assert contracts_deployed_path(chain_id, version, services).exists()


def reasonable_deployment_of_a_contract(deployed: DeployedContract) -> None:
    """Checks an entry under deployment_*.json under a contract name"""
    assert isinstance(deployed["address"], str)
    assert len(deployed["address"]) == 42
    assert isinstance(deployed["transaction_hash"], str)
    assert len(deployed["transaction_hash"]) == 66
    assert isinstance(deployed["block_number"], int)
    assert deployed["block_number"] > 0
    assert isinstance(deployed["gas_cost"], int)
    assert deployed["gas_cost"] > 0
    assert isinstance(deployed["constructor_arguments"], list)


RAIDEN_CONTRACT_NAMES = ("TokenNetworkRegistry", "SecretRegistry")


@pytest.mark.parametrize("version", [None])
@pytest.mark.parametrize("chain_id", [3, 4, 5])
def test_deploy_data_has_fields_raiden(version: Optional[str], chain_id: ChainID) -> None:
    data = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.RAIDEN)
    assert data
    assert data["contracts_version"] == version if version else CONTRACTS_VERSION
    assert data["chain_id"] == chain_id
    contracts = data["contracts"]
    for name in RAIDEN_CONTRACT_NAMES:
        deployed = contracts[name]
        reasonable_deployment_of_a_contract(deployed)


SERVICE_CONTRACT_NAMES = (
    "ServiceRegistry",
    "MonitoringService",
    "OneToN",
    "UserDeposit",
)


@pytest.mark.parametrize("version", [None])
@pytest.mark.parametrize("chain_id", [3, 4, 5])
def test_deploy_data_has_fields_services(version: Optional[str], chain_id: ChainID) -> None:
    data = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.SERVICES)
    assert data
    assert data["contracts_version"] == version if version else CONTRACTS_VERSION
    assert data["chain_id"] == chain_id
    contracts = data["contracts"]
    for name in SERVICE_CONTRACT_NAMES:
        deployed = contracts[name]
        reasonable_deployment_of_a_contract(deployed)


@pytest.mark.parametrize("version", [None])
@pytest.mark.parametrize("chain_id", [3, 4, 5])
def test_deploy_data_all(version: Optional[str], chain_id: ChainID) -> None:
    data_all = get_contracts_deployment_info(chain_id, version, module=DeploymentModule.ALL)
    data_default = get_contracts_deployment_info(chain_id, version)
    assert data_all
    assert data_all == data_default

    for name in RAIDEN_CONTRACT_NAMES + SERVICE_CONTRACT_NAMES:
        deployed = data_all["contracts"][name]
        reasonable_deployment_of_a_contract(deployed)


def test_deploy_data_unknown_module() -> None:
    with pytest.raises(ValueError):
        get_contracts_deployment_info(3, None, module=None)  # type: ignore


def test_deploy_data_not_deployed() -> None:
    assert (
        get_contracts_deployment_info(ChainID(1), "0.8.0", module=DeploymentModule.RAIDEN) is None
    )


@pytest.mark.parametrize("chain_id", [3, 4, 42])
def test_deploy_data_for_redeyes_succeed(chain_id: ChainID) -> None:
    """get_contracts_deployment_info() on RedEyes version should return a non-empty dictionary"""
    assert get_contracts_deployment_info(chain_id, "0.4.0")


@pytest.mark.parametrize("chain_id", [3, 4, 5, 42])
def test_service_deploy_data_for_redeyes_fail(chain_id: ChainID) -> None:
    """get_contracts_deployment_info() on RedEyes version should return a non-empty dictionary"""
    with pytest.raises(ValueError):
        assert get_contracts_deployment_info(chain_id, "0.4.0", DeploymentModule.SERVICES)


@pytest.mark.parametrize("chain_id", [1, 3, 4, 5])
def test_deploy_data_for_alderaan_exist(chain_id: ChainID) -> None:
    """get_contracts_deployment_info() on Alderaan version should have data"""
    assert get_contracts_deployment_info(chain_id, ALDERAAN_VERSION)
    assert get_contracts_deployment_info(chain_id, ALDERAAN_VERSION, DeploymentModule.SERVICES)


def test_version_provides_services() -> None:
    assert contracts_version_provides_services(CONTRACTS_VERSION)
    with pytest.raises(ValueError):
        assert contracts_version_provides_services("not a semver")


def test_verify_nonexistent_deployment(
    user_deposit_whole_balance_limit: int, token_network_registry_address: HexAddress
) -> None:
    """Test verify_deployed_contracts_in_filesystem() with a non-existent deployment data."""
    web3_mock = Mock()
    web3_mock.version.network = 42
    # contracts_version 0.37.0 does not contain a kovan deployment.
    verifier = ContractVerifier(web3=web3_mock, contracts_version=ALDERAAN_VERSION)
    with pytest.raises(RuntimeError):
        verifier.verify_deployed_contracts_in_filesystem()
    with pytest.raises(RuntimeError):
        verifier.verify_deployed_service_contracts_in_filesystem(
            token_address=EMPTY_ADDRESS,
            user_deposit_whole_balance_limit=user_deposit_whole_balance_limit,
            token_network_registry_address=token_network_registry_address,
        )


def test_verify_existent_deployment(token_network_registry_contract: Contract) -> None:
    """Test verify_deployed_contracts_in_filesystem() with an existent deployment data

    but with a fake web3 that returns a wrong block number for deployment.
    """
    web3_mock = Mock()
    web3_mock.version.network = 5
    web3_mock.eth.get_transaction_receipt = lambda _: {"blockNumber": 0}
    verifier = ContractVerifier(web3=web3_mock, contracts_version=ALDERAAN_VERSION)
    # The Mock returns a wrong block number, so the comparison fails.
    with pytest.raises(RuntimeError):
        verifier.verify_deployed_contracts_in_filesystem()
    with pytest.raises(RuntimeError):
        verifier.verify_deployed_service_contracts_in_filesystem(
            token_address=HexAddress(HexStr("0x5Fc523e13fBAc2140F056AD7A96De2cC0C4Cc63A")),
            user_deposit_whole_balance_limit=2**256 - 1,
            token_network_registry_address=token_network_registry_contract.address,
        )


def test_verify_existent_deployment_with_wrong_code(
    token_network_registry_contract: Contract,
) -> None:
    """Test verify_deployed_contracts_in_filesystem() with an existent deployment data

    but with a fake web3 that does not return the correct code.
    """
    web3_mock = Mock()
    web3_mock.version.network = 5
    web3_mock.eth.get_transaction_receipt = lambda _: {
        "blockNumber": 10711807,
        "gasUsed": 555366,
        "contractAddress": "0x8Ff327f7ed03cD6Bd5e611E9e404B47d8c9Db81E",
    }
    verifier = ContractVerifier(web3=web3_mock, contracts_version=ALDERAAN_VERSION)
    # The Mock returns a wrong block number, so the comparison fails.
    with pytest.raises(RuntimeError):
        verifier.verify_deployed_contracts_in_filesystem()
    with pytest.raises(RuntimeError):
        verifier.verify_deployed_service_contracts_in_filesystem(
            token_address=HexAddress(HexStr("0x5Fc523e13fBAc2140F056AD7A96De2cC0C4Cc63A")),
            user_deposit_whole_balance_limit=2**256 - 1,
            token_network_registry_address=token_network_registry_contract.address,
        )
