import json
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Generator, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from click import BadParameter, NoSuchOption
from click.testing import CliRunner
from eth_typing import HexStr
from eth_typing.evm import ChecksumAddress, HexAddress
from eth_utils import ValidationError, to_checksum_address
from pyfakefs.fake_filesystem import FakeFilesystem
from pyfakefs.fake_filesystem_unittest import Patcher
from web3 import Web3
from web3.contract import Contract
from web3.eth import Eth

import raiden_contracts
from raiden_contracts.constants import (
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    DEPLOY_SETTLE_TIMEOUT_MAX,
    DEPLOY_SETTLE_TIMEOUT_MIN,
    EMPTY_ADDRESS,
)
from raiden_contracts.contract_manager import DeployedContracts, contracts_precompiled_path
from raiden_contracts.deploy.__main__ import (
    ContractDeployer,
    ContractVerifier,
    contracts_version_with_max_token_networks,
    error_removed_option,
    raiden,
    register,
    services,
    token,
    validate_address,
    verify,
)
from raiden_contracts.deploy.contract_deployer import (
    contracts_version_monitoring_service_takes_token_network_registry,
)
from raiden_contracts.deploy.contract_verifier import (
    _verify_monitoring_service_deployment,
    _verify_user_deposit_deployment,
)
from raiden_contracts.tests.utils import FAKE_ADDRESS, get_random_privkey
from raiden_contracts.tests.utils.constants import (
    DEPLOYER_ADDRESS,
    FAUCET_PRIVATE_KEY,
    SECONDS_PER_DAY,
    SERVICE_DEPOSIT,
    UINT256_MAX,
)
from raiden_contracts.utils.versions import contracts_version_has_initial_service_deposit

GAS_LIMIT = 5860000


@pytest.fixture(scope="session")
def deployer(web3: Web3) -> ContractDeployer:
    return ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=GAS_LIMIT,
        gas_price=1,
        wait=10,
        contracts_version=None,
    )


@pytest.fixture(scope="session")
def deployer_0_4_0(web3: Web3) -> ContractDeployer:
    return ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=GAS_LIMIT,
        gas_price=1,
        wait=10,
        contracts_version="0.4.0",
    )


@pytest.fixture(scope="session")
def deployer_0_21_0(web3: Web3) -> ContractDeployer:
    return ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=GAS_LIMIT,
        gas_price=1,
        wait=10,
        contracts_version="0.21.0",
    )


@pytest.mark.slow
@pytest.fixture(scope="session")
def deployed_raiden_info(deployer: ContractDeployer) -> DeployedContracts:
    return deployer.deploy_raiden_contracts(
        max_num_of_token_networks=1,
        reuse_secret_registry_from_deploy_file=None,
        settle_timeout_min=DEPLOY_SETTLE_TIMEOUT_MIN,
        settle_timeout_max=DEPLOY_SETTLE_TIMEOUT_MAX,
    )


@pytest.mark.slow
@pytest.fixture(scope="session")
def deployed_raiden_info2(deployer: ContractDeployer) -> DeployedContracts:
    return deployer.deploy_raiden_contracts(
        max_num_of_token_networks=1,
        reuse_secret_registry_from_deploy_file=None,
        settle_timeout_min=DEPLOY_SETTLE_TIMEOUT_MIN,
        settle_timeout_max=DEPLOY_SETTLE_TIMEOUT_MAX,
    )


@pytest.mark.slow
@pytest.fixture(scope="session")
def deployed_raiden_info_0_4_0(deployer_0_4_0: ContractDeployer) -> DeployedContracts:
    return deployer_0_4_0.deploy_raiden_contracts(
        max_num_of_token_networks=None,
        reuse_secret_registry_from_deploy_file=None,
        settle_timeout_min=DEPLOY_SETTLE_TIMEOUT_MIN,
        settle_timeout_max=DEPLOY_SETTLE_TIMEOUT_MAX,
    )


TOKEN_SUPPLY = 10000000


@pytest.fixture(scope="session")
def token_address(deployer: ContractDeployer) -> HexAddress:
    token_type = "CustomToken"
    deployed_token = deployer.deploy_token_contract(
        token_supply=TOKEN_SUPPLY,
        token_decimals=18,
        token_name="TestToken",
        token_symbol="TTT",
        token_type=token_type,
    )
    return deployed_token[token_type]


DEPOSIT_LIMIT = TOKEN_SUPPLY // 2


@pytest.mark.slow
@pytest.fixture(scope="session")
def deployed_service_info(
    deployer: ContractDeployer,
    token_address: HexAddress,
    token_network_registry_contract: Contract,
) -> DeployedContracts:
    return deployer.deploy_service_contracts(
        token_address=token_address,
        user_deposit_whole_balance_limit=DEPOSIT_LIMIT,
        service_registry_controller=DEPLOYER_ADDRESS,
        initial_service_deposit_price=SERVICE_DEPOSIT // 2,
        service_deposit_bump_numerator=6,
        service_deposit_bump_denominator=5,
        decay_constant=200 * SECONDS_PER_DAY,
        min_price=1000,
        registration_duration=180 * SECONDS_PER_DAY,
        token_network_registry_address=token_network_registry_contract.address,
    )


@pytest.mark.slow
@pytest.fixture(scope="session")
def test_deploy_service_0_4_0(
    deployer_0_4_0: ContractDeployer,
    token_address: HexAddress,
    token_network_registry_contract: Contract,
) -> None:
    with pytest.raises(RuntimeError, match="older service contracts is not supported"):
        deployer_0_4_0.deploy_service_contracts(
            token_address=token_address,
            user_deposit_whole_balance_limit=DEPOSIT_LIMIT,
            service_registry_controller=DEPLOYER_ADDRESS,
            initial_service_deposit_price=SERVICE_DEPOSIT // 2,
            service_deposit_bump_numerator=6,
            service_deposit_bump_denominator=5,
            decay_constant=200 * SECONDS_PER_DAY,
            min_price=1000,
            registration_duration=180 * SECONDS_PER_DAY,
            token_network_registry_address=token_network_registry_contract.address,
        )


@pytest.mark.slow
@pytest.fixture(scope="session")
def test_deploy_service_0_21_0(
    deployer_0_21_0: ContractDeployer,
    token_address: HexAddress,
    token_network_registry_contract: Contract,
) -> None:
    with pytest.raises(RuntimeError, match="older service contracts is not supported"):
        deployer_0_21_0.deploy_service_contracts(
            token_address=token_address,
            user_deposit_whole_balance_limit=DEPOSIT_LIMIT,
            service_registry_controller=DEPLOYER_ADDRESS,
            initial_service_deposit_price=SERVICE_DEPOSIT // 2,
            service_deposit_bump_numerator=6,
            service_deposit_bump_denominator=5,
            decay_constant=200 * SECONDS_PER_DAY,
            min_price=1000,
            registration_duration=180 * SECONDS_PER_DAY,
            token_network_registry_address=token_network_registry_contract.address,
        )


@pytest.mark.parametrize(
    "version,expectation",
    [
        ("0.3._", False),
        ("0.4.0", False),
        ("0.8.0", False),
        ("0.9.0", True),
        ("0.10.0", True),
        (None, True),
    ],
)
def test_contracts_version_with_max_token_networks(
    version: Optional[str], expectation: bool
) -> None:
    assert contracts_version_with_max_token_networks(version) == expectation


@pytest.mark.parametrize(
    "version,expectation",
    [
        ("0.3.0", False),
        ("0.3._", False),
        ("0.4.0", False),
        ("0.8.0", False),
        ("0.8.0_unlimited", False),
        ("0.22.0", False),
        ("0.23.0", True),
        (None, True),
    ],
)
def test_contracts_version_monitoring_service_takes_token_network_registry(
    version: Optional[str], expectation: bool
) -> None:
    assert (
        contracts_version_monitoring_service_takes_token_network_registry(version) == expectation
    )


@pytest.mark.slow
def test_deploy_script_raiden(
    web3: Web3,
    deployer: ContractDeployer,
    deployed_raiden_info: DeployedContracts,
    deployed_raiden_info2: DeployedContracts,
) -> None:
    """ Run raiden contracts deployment function and tamper with deployed_contracts_info

    This checks if deploy_raiden_contracts() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    This also tampers with deployed_contracts_info to make sure an error is raised in
    verify_deployed_contracts()
    """
    deployed_contracts_info = deployed_raiden_info

    deployer.verify_deployment_data(deployment_data=deployed_contracts_info)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts_version"] = "0.0.0"
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployment_data=deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["chain_id"] = 0
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployment_data=deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_SECRET_REGISTRY]["address"] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_SECRET_REGISTRY]["address"] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "address"
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_SECRET_REGISTRY]["block_number"] = 0
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_SECRET_REGISTRY]["block_number"] = 0
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY]["block_number"] = 0
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY]["gas_cost"] = 0
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "address"
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts_version"] = "0.4.0"
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_SECRET_REGISTRY] = deployed_raiden_info2[
        "contracts"
    ][CONTRACT_SECRET_REGISTRY]
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "constructor_arguments"
    ][0] = DEPLOYER_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "constructor_arguments"
    ][1] = DEPLOYER_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "constructor_arguments"
    ] = []
    with pytest.raises(RuntimeError):
        deployer.verify_deployment_data(deployed_contracts_info_fail)

    # check that it fails if sender has no eth
    deployer = ContractDeployer(
        web3=web3, private_key=get_random_privkey(), gas_limit=GAS_LIMIT, gas_price=1, wait=10
    )
    with pytest.raises(ValidationError):
        deployer.deploy_raiden_contracts(
            1,
            reuse_secret_registry_from_deploy_file=None,
            settle_timeout_min=DEPLOY_SETTLE_TIMEOUT_MIN,
            settle_timeout_max=DEPLOY_SETTLE_TIMEOUT_MAX,
        )


def test_deploy_raiden_reuse_secret_registry(
    deployer: ContractDeployer, deployed_raiden_info: DeployedContracts
) -> None:
    """ Run deploy_raiden_contracts with a previous SecretRegistry deployment data """
    with NamedTemporaryFile() as previous_deployment_file:
        previous_deployment_file.write(bytearray(json.dumps(deployed_raiden_info), "ascii"))
        previous_deployment_file.flush()
        new_deployment = deployer.deploy_raiden_contracts(
            1,
            reuse_secret_registry_from_deploy_file=Path(previous_deployment_file.name),
            settle_timeout_min=DEPLOY_SETTLE_TIMEOUT_MIN,
            settle_timeout_max=DEPLOY_SETTLE_TIMEOUT_MAX,
        )
        assert (
            new_deployment["contracts"][CONTRACT_SECRET_REGISTRY]
            == deployed_raiden_info["contracts"][CONTRACT_SECRET_REGISTRY]
        )
        assert (
            new_deployment["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY]
            != deployed_raiden_info["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY]
        )


def test_deploy_script_token(web3: Web3) -> None:
    """ Run test token deployment function used in the deployment script

    This checks if deploy_token_contract() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    """
    # normal deployment
    token_type = "CustomToken"
    gas_limit = 5860000
    deployer = ContractDeployer(
        web3=web3, private_key=FAUCET_PRIVATE_KEY, gas_limit=gas_limit, gas_price=1, wait=10
    )

    deployed_token = deployer.deploy_token_contract(
        token_supply=10000000,
        token_decimals=18,
        token_name="TestToken",
        token_symbol="TTT",
        token_type=token_type,
    )

    assert deployed_token[token_type] is not None
    assert isinstance(deployed_token[token_type], str)

    # check that it fails if sender has no eth
    deployer = ContractDeployer(
        web3=web3, private_key=get_random_privkey(), gas_limit=gas_limit, gas_price=1, wait=10
    )
    with pytest.raises(ValidationError):
        deployer.deploy_token_contract(
            token_supply=10000000,
            token_decimals=18,
            token_name="TestToken",
            token_symbol="TTT",
            token_type="CustomToken",
        )


@pytest.mark.slow
def test_deploy_script_register(
    web3: Web3,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
    deployed_raiden_info: DeployedContracts,
    token_address: ChecksumAddress,
) -> None:
    """ Run token register function used in the deployment script

    This checks if register_token_network() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    """
    # normal deployment
    gas_limit = 5860000
    deployer = ContractDeployer(
        web3=web3, private_key=FAUCET_PRIVATE_KEY, gas_limit=gas_limit, gas_price=1, wait=10
    )

    deployed_contracts_raiden = deployed_raiden_info
    token_registry_abi = deployer.contract_manager.get_contract_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY
    )
    token_registry_address = deployed_contracts_raiden["contracts"][
        CONTRACT_TOKEN_NETWORK_REGISTRY
    ]["address"]
    token_network_address = deployer.register_token_network(
        token_registry_abi=token_registry_abi,
        token_registry_address=token_registry_address,
        token_address=token_address,
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
    )
    assert token_network_address is not None
    assert isinstance(token_network_address, str)


def test_deploy_script_register_missing_limits(
    token_network_deposit_limit: int,
    channel_participant_deposit_limit: int,
    deployed_raiden_info: DeployedContracts,
    token_address: ChecksumAddress,
    deployer: ContractDeployer,
) -> None:
    """ Run token register function used in the deployment script

    without the expected channel participant deposit limit.
    """
    token_registry_abi = deployer.contract_manager.get_contract_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY
    )
    token_registry_address = deployed_raiden_info["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "address"
    ]
    with pytest.raises(ValueError):
        deployer.register_token_network(
            token_registry_abi=token_registry_abi,
            token_registry_address=token_registry_address,
            token_address=token_address,
            channel_participant_deposit_limit=None,
            token_network_deposit_limit=token_network_deposit_limit,
        )
    with pytest.raises(ValueError):
        deployer.register_token_network(
            token_registry_abi=token_registry_abi,
            token_registry_address=token_registry_address,
            token_address=token_address,
            channel_participant_deposit_limit=channel_participant_deposit_limit,
            token_network_deposit_limit=None,
        )
    with pytest.raises(ValueError):
        deployer.register_token_network(
            token_registry_abi=token_registry_abi,
            token_registry_address=token_registry_address,
            token_address=token_address,
            channel_participant_deposit_limit=None,
            token_network_deposit_limit=None,
        )


def test_deploy_script_register_unexpected_limits(
    web3: Web3,
    token_network_deposit_limit: int,
    channel_participant_deposit_limit: int,
    token_address: ChecksumAddress,
    deployed_raiden_info: DeployedContracts,
) -> None:
    """ Run token register function used in the deployment script

    on contracts before the limits were introduced. We don't support that, anymore.
    """
    deployer = ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=GAS_LIMIT,
        gas_price=1,
        wait=10,
        contracts_version="0.4.0",
    )

    token_registry_abi = deployer.contract_manager.get_contract_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY
    )
    token_registry_address = deployed_raiden_info["contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY][
        "address"
    ]
    with pytest.raises(AssertionError, match="Can't deploy old contracts.*limits"):
        deployer.register_token_network(
            token_registry_abi=token_registry_abi,
            token_registry_address=token_registry_address,
            token_address=token_address,
            channel_participant_deposit_limit=channel_participant_deposit_limit,
            token_network_deposit_limit=token_network_deposit_limit,
        )


@pytest.mark.slow
def test_deploy_script_service(
    web3: Web3,
    deployed_service_info: DeployedContracts,
    token_address: HexAddress,
    token_network_registry_contract: Contract,
) -> None:
    """ Run deploy_service_contracts() used in the deployment script

    This checks if deploy_service_contracts() works correctly in the happy case.
    """
    gas_limit = 5860000
    deployer = ContractDeployer(
        web3=web3, private_key=FAUCET_PRIVATE_KEY, gas_limit=gas_limit, gas_price=1, wait=10
    )

    token_supply = 10000000
    assert isinstance(token_address, str)
    deposit_limit = token_supply // 2

    deployed_service_contracts = deployed_service_info
    deployer.verify_service_contracts_deployment_data(
        token_address=token_address,
        user_deposit_whole_balance_limit=deposit_limit,
        deployed_contracts_info=deployed_service_contracts,
        token_network_registry_address=token_network_registry_contract.address,
    )

    with pytest.raises(RuntimeError):
        assert EMPTY_ADDRESS != token_address
        deployer.verify_service_contracts_deployment_data(
            token_address=EMPTY_ADDRESS,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_service_contracts,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts_version"] = "0.0.0"
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["chain_id"] = deployed_service_contracts["chain_id"] + 1
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_SERVICE_REGISTRY]["constructor_arguments"] = [
        EMPTY_ADDRESS
    ]
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_SERVICE_REGISTRY]["constructor_arguments"][
        0
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    original = deployed_info_fail["contracts"][CONTRACT_USER_DEPOSIT]["constructor_arguments"]
    deployed_info_fail["contracts"][CONTRACT_USER_DEPOSIT]["constructor_arguments"] += original
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_USER_DEPOSIT]["constructor_arguments"][
        0
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_USER_DEPOSIT]["constructor_arguments"][1] = (
        deposit_limit + 1
    )
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    original = deployed_info_fail["contracts"][CONTRACT_MONITORING_SERVICE][
        "constructor_arguments"
    ]
    deployed_info_fail["contracts"][CONTRACT_MONITORING_SERVICE][
        "constructor_arguments"
    ] += original
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_MONITORING_SERVICE]["constructor_arguments"][
        0
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_MONITORING_SERVICE]["constructor_arguments"][
        2
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_MONITORING_SERVICE]["constructor_arguments"][
        3
    ] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_ONE_TO_N]["constructor_arguments"][0] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_ONE_TO_N]["constructor_arguments"][1] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail["contracts"][CONTRACT_ONE_TO_N]["constructor_arguments"][2] = EMPTY_ADDRESS
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    original = deployed_info_fail["contracts"][CONTRACT_ONE_TO_N]["constructor_arguments"]
    deployed_info_fail["contracts"][CONTRACT_ONE_TO_N]["constructor_arguments"] += original
    with pytest.raises(RuntimeError):
        deployer.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployed_contracts_info=deployed_info_fail,
            token_network_registry_address=token_network_registry_contract.address,
        )

    def test_missing_deployment(contract_name: str) -> None:
        deployed_info_fail = deepcopy(deployed_service_contracts)
        deployed_info_fail["contracts"][contract_name]["address"] = EMPTY_ADDRESS
        with pytest.raises(RuntimeError):
            deployer.verify_service_contracts_deployment_data(
                token_address=token_address,
                user_deposit_whole_balance_limit=deposit_limit,
                deployed_contracts_info=deployed_info_fail,
                token_network_registry_address=token_network_registry_contract.address,
            )

    for contract_name in [
        CONTRACT_SERVICE_REGISTRY,
        CONTRACT_MONITORING_SERVICE,
        CONTRACT_ONE_TO_N,
        CONTRACT_USER_DEPOSIT,
    ]:
        test_missing_deployment(contract_name)


def test_validate_address_on_none() -> None:
    """ validate_address(x, y, None) should return None """
    mock_command = MagicMock()
    mock_parameter = MagicMock()
    assert validate_address(mock_command, mock_parameter, None) is None


def test_validate_address_empty_string() -> None:
    """ validate_address(x, y, '') should return None """
    assert validate_address(MagicMock(), MagicMock(), "") is None


def test_validate_address_not_an_address() -> None:
    """ validate_address(x, y, 'not an address') should raise click.BadParameter """
    with pytest.raises(BadParameter):
        validate_address(MagicMock(), MagicMock(), "not an address")


def test_validate_address_happy_path() -> None:
    """ validate_address(x, y, address) should return the same address checksumed """
    address = DEPLOYER_ADDRESS
    assert validate_address(MagicMock(), MagicMock(), address) == to_checksum_address(address)


@pytest.fixture
def fs_reload_deployer() -> Generator[FakeFilesystem, None, None]:
    patcher = Patcher(
        modules_to_reload=[raiden_contracts.contract_manager, raiden_contracts.deploy.__main__]
    )
    patcher.setUp()
    yield patcher.fs
    patcher.tearDown()


@pytest.mark.slow
def test_store_and_verify_raiden(
    fs_reload_deployer: FakeFilesystem,
    deployed_raiden_info: DeployedContracts,
    deployer: ContractDeployer,
) -> None:
    """ Store some raiden contract deployment information and verify them """
    fs_reload_deployer.add_real_directory(
        contracts_precompiled_path(version=None).parent, read_only=False
    )
    deployed_contracts_info = deployed_raiden_info
    deployer.store_and_verify_deployment_info_raiden(
        deployed_contracts_info=deployed_contracts_info
    )
    deployer.store_and_verify_deployment_info_raiden(
        deployed_contracts_info=deployed_contracts_info
    )


@pytest.mark.slow
def test_store_and_verify_services(
    fs_reload_deployer: FakeFilesystem,
    deployer: ContractDeployer,
    deployed_service_info: DeployedContracts,
    token_address: HexAddress,
    token_network_registry_contract: Contract,
) -> None:
    """ Store some service contract deployment information and verify them """
    fs_reload_deployer.add_real_directory(
        contracts_precompiled_path(version=None).parent, read_only=False
    )
    deployed_contracts_info = deployed_service_info
    deployer.verify_service_contracts_deployment_data(
        token_address=token_address,
        deployed_contracts_info=deployed_contracts_info,
        user_deposit_whole_balance_limit=DEPOSIT_LIMIT,
        token_network_registry_address=token_network_registry_contract.address,
    )
    deployer.store_and_verify_deployment_info_services(
        token_address=token_address,
        deployed_contracts_info=deployed_contracts_info,
        user_deposit_whole_balance_limit=DEPOSIT_LIMIT,
        token_network_registry_address=token_network_registry_contract.address,
    )


@pytest.mark.slow
def test_red_eyes_deployer(web3: Web3) -> None:
    """ A smoke test for deploying RedEyes version contracts """
    deployer = ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=GAS_LIMIT,
        gas_price=1,
        wait=10,
        contracts_version="0.4.0",
    )
    deployer.deploy_raiden_contracts(
        max_num_of_token_networks=None,
        reuse_secret_registry_from_deploy_file=None,
        settle_timeout_min=DEPLOY_SETTLE_TIMEOUT_MIN,
        settle_timeout_max=DEPLOY_SETTLE_TIMEOUT_MAX,
    )


def test_error_removed_option_raises() -> None:
    with pytest.raises(NoSuchOption):
        mock = MagicMock()
        error_removed_option("msg")(None, mock, "0xaabbcc")


def test_contracts_version_has_initial_service_deposit() -> None:
    assert not contracts_version_has_initial_service_deposit("0.3._")
    assert not contracts_version_has_initial_service_deposit("0.4.0")
    assert not contracts_version_has_initial_service_deposit("0.8.0_unlimited")
    assert not contracts_version_has_initial_service_deposit("0.9.0")
    assert not contracts_version_has_initial_service_deposit("0.10.0")
    assert not contracts_version_has_initial_service_deposit("0.10.1")
    assert contracts_version_has_initial_service_deposit(None)
    with pytest.raises(ValueError):
        contracts_version_has_initial_service_deposit("not a semver string")


def deploy_token_arguments(privkey: str) -> List[str]:
    return [
        "--rpc-provider",
        "rpc_provider",
        "--private-key",
        privkey,
        "--gas-price",
        "12",
        "--token-supply",
        "20000000",
        "--token-name",
        "ServiceToken",
        "--token-decimals",
        "18",
        "--token-symbol",
        "SVT",
    ]


def test_deploy_token_invalid_privkey() -> None:
    """ Call deploy token command with invalid private key """
    with patch.object(
        ContractDeployer, "deploy_token_contract", spec=ContractDeployer
    ) as mock_deployer:
        runner = CliRunner()
        result = runner.invoke(token, deploy_token_arguments(privkey="wrong_priv_key"))
        assert result.exit_code != 0
        assert type(result.exception) == RuntimeError
        assert result.exception.args == ("Could not access the private key.",)
        mock_deployer.assert_not_called()


def test_deploy_token_no_balance(get_accounts: Callable, get_private_key: Callable) -> None:
    """ Call deploy token command with a private key with no balance """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(
            ContractDeployer, "deploy_token_contract", spec=ContractDeployer
        ) as mock_deployer:
            with patch.object(Eth, "getBalance", return_value=0):
                runner = CliRunner()
                result = runner.invoke(token, deploy_token_arguments(privkey=privkey_file.name))
                assert result.exit_code != 0
                assert type(result.exception) == RuntimeError
                assert result.exception.args == ("Account with insufficient funds.",)
                mock_deployer.assert_not_called()


def test_deploy_token_with_balance(get_accounts: Callable, get_private_key: Callable) -> None:
    """ Call deploy token command with a private key with some balance """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(
            ContractDeployer, "deploy_token_contract", spec=ContractDeployer, return_value={}
        ) as mock_deployer:
            with patch.object(Eth, "getBalance", return_value=100):
                runner = CliRunner()
                result = runner.invoke(token, deploy_token_arguments(privkey=privkey_file.name))
                assert result.exit_code == 0
                mock_deployer.assert_called_once()


def deploy_raiden_arguments(
    privkey: str,
    save_info: Optional[bool],
    contracts_version: Optional[str],
    reuse_secret_registry: bool,
) -> List:
    arguments: List = ["--private-key", privkey, "--rpc-provider", "rpc_provider"]

    if save_info is True:
        arguments.append("--save-info")
    elif save_info is False:
        arguments.append("--no-save-info")

    if contracts_version_with_max_token_networks(contracts_version):
        arguments.extend(["--max-token-networks", 1])

    if contracts_version:
        arguments.extend(["--contracts-version", contracts_version])

    if reuse_secret_registry:
        arguments.extend(["--secret-registry-from-deployment-file", "."])

    return arguments


@patch.object(ContractDeployer, "deploy_raiden_contracts")
@patch.object(ContractVerifier, "store_and_verify_deployment_info_raiden")
@pytest.mark.parametrize("contracts_version", [None, "0.4.0"])
@pytest.mark.parametrize("reuse_secret_registry", [False, True])
def test_deploy_raiden(
    mock_deploy: MagicMock,
    mock_verify: MagicMock,
    get_accounts: Callable,
    get_private_key: Callable,
    contracts_version: Optional[str],
    reuse_secret_registry: bool,
) -> None:
    """ Calling deploy raiden command """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                raiden,
                deploy_raiden_arguments(
                    privkey=privkey_file.name,
                    save_info=None,
                    contracts_version=contracts_version,
                    reuse_secret_registry=reuse_secret_registry,
                ),
            )
            assert result.exception is None
            assert result.exit_code == 0
            mock_deploy.assert_called_once()
            mock_verify.assert_called_once()


@patch.object(ContractDeployer, "register_token_network")
def test_register_script(
    mock_deploy: MagicMock, get_accounts: Callable, get_private_key: Callable
) -> None:
    """ Calling deploy raiden command """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                register,
                [
                    "--rpc-provider",
                    "rpv_provider",
                    "--private-key",
                    privkey_file.name,
                    "--gas-price",
                    "12",
                    "--token-network-registry-address",
                    "0x90a16f6aEA062c429c85dc4124ee4b24A00bCc9a",
                    "--token-address",
                    "0x90a16f6aEA062c429c85dc4124ee4b24A00bCc9a",
                    "--channel-participant-deposit-limit",
                    "100",
                    "--token-network-deposit-limit",
                    "200",
                ],
            )
            assert result.exception is None
            assert result.exit_code == 0
            mock_deploy.assert_called_once()


@patch.object(ContractDeployer, "register_token_network")
def test_register_script_without_token_network(
    mock_deploy: MagicMock, get_accounts: Callable, get_private_key: Callable
) -> None:
    """ Calling deploy raiden command """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                register,
                [
                    "--rpc-provider",
                    "rpv_provider",
                    "--private-key",
                    privkey_file.name,
                    "--gas-price",
                    "12",
                    "--token-address",
                    "0x90a16f6aEA062c429c85dc4124ee4b24A00bCc9a",
                    "--channel-participant-deposit-limit",
                    "100",
                    "--token-network-deposit-limit",
                    "200",
                ],
            )
            assert result.exit_code != 0
            assert type(result.exception) == RuntimeError
            assert result.exception.args == (
                "No TokenNetworkRegistry was specified. "
                "Add --token-network-registry-address <address>.",
            )
            mock_deploy.assert_not_called()


@patch.object(ContractDeployer, "deploy_raiden_contracts")
@patch.object(ContractDeployer, "verify_deployment_data")
def test_deploy_raiden_save_info_false(
    mock_deploy: MagicMock,
    mock_verify: MagicMock,
    get_accounts: Callable,
    get_private_key: Callable,
) -> None:
    """ Calling deploy raiden command with --save_info False"""
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                raiden,
                deploy_raiden_arguments(
                    privkey=privkey_file.name,
                    save_info=False,
                    contracts_version=None,
                    reuse_secret_registry=False,
                ),
            )
            assert result.exception is None
            assert result.exit_code == 0
            mock_deploy.assert_called_once()
            mock_verify.assert_called_once()


def deploy_services_arguments(
    privkey: str,
    save_info: Optional[bool],
    service_registry_controller: HexAddress,
    token_network_registry_address: HexAddress,
    contracts_version: Optional[str] = None,
) -> List:
    if save_info is None:
        arguments: List = []
    elif save_info is True:
        arguments = ["--save-info"]
    else:
        arguments = ["--no-save-info"]

    if contracts_version is not None:
        arguments += ["--contracts_version", contracts_version]

    arguments += [
        "--private-key",
        privkey,
        "--rpc-provider",
        "rpc_provider",
        "--user-deposit-whole-limit",
        100,
        "--initial-service-deposit-price",
        SERVICE_DEPOSIT // 2,
        "--service-registry-controller",
        service_registry_controller,
        "--service-deposit-bump-numerator",
        6,
        "--service-deposit-bump-denominator",
        5,
        "--service-deposit-decay-constant",
        200 * SECONDS_PER_DAY,
        "--service-deposit-min-price",
        1000,
        "--service-registration-duration",
        180 * SECONDS_PER_DAY,
        "--token-network-registry-address",
        token_network_registry_address,
    ]
    return arguments


@patch.object(ContractDeployer, "deploy_service_contracts")
@patch.object(ContractVerifier, "store_and_verify_deployment_info_services")
def test_deploy_services(
    mock_deploy: MagicMock,
    mock_verify: MagicMock,
    get_accounts: Callable,
    get_private_key: Callable,
) -> None:
    """ Calling deploy raiden command """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                services,
                deploy_services_arguments(
                    privkey=privkey_file.name,
                    save_info=None,
                    service_registry_controller=FAKE_ADDRESS,
                    token_network_registry_address=FAKE_ADDRESS,
                ),
            )
            assert result.exception is None
            assert result.exit_code == 0
            mock_deploy.assert_called_once()
            mock_verify.assert_called_once()


def test_deploy_old_services(get_accounts: Callable, get_private_key: Callable) -> None:
    """ Calling deploy raiden command """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                services,
                deploy_services_arguments(
                    privkey=privkey_file.name,
                    save_info=None,
                    service_registry_controller=FAKE_ADDRESS,
                    token_network_registry_address=FAKE_ADDRESS,
                    contracts_version="0.21.0",
                ),
            )
            assert result.exception
            assert result.exit_code == 2


@patch.object(ContractDeployer, "deploy_service_contracts")
@patch.object(ContractVerifier, "store_and_verify_deployment_info_services")
def test_deploy_services_with_controller(
    mock_deploy: MagicMock,
    mock_verify: MagicMock,
    get_accounts: Callable,
    get_private_key: Callable,
) -> None:
    """ Calling deploy raiden command """
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                services,
                deploy_services_arguments(
                    privkey=privkey_file.name,
                    save_info=None,
                    service_registry_controller=signer,
                    token_network_registry_address=FAKE_ADDRESS,
                ),
            )
            assert result.exception is None
            assert result.exit_code == 0
            mock_deploy.assert_called_once()
            mock_verify.assert_called_once()


@patch.object(ContractDeployer, "deploy_service_contracts")
@patch.object(ContractDeployer, "verify_service_contracts_deployment_data")
def test_deploy_services_save_info_false(
    mock_deploy: MagicMock,
    mock_verify: MagicMock,
    get_accounts: Callable,
    get_private_key: Callable,
) -> None:
    """ Calling deploy raiden command with --save_info False"""
    (signer,) = get_accounts(1)
    priv_key = get_private_key(signer)
    with NamedTemporaryFile() as privkey_file:
        privkey_file.write(bytearray(priv_key, "ascii"))
        privkey_file.flush()
        with patch.object(Eth, "getBalance", return_value=1):
            runner = CliRunner()
            result = runner.invoke(
                services,
                deploy_services_arguments(
                    privkey=privkey_file.name,
                    save_info=False,
                    service_registry_controller=FAKE_ADDRESS,
                    token_network_registry_address=FAKE_ADDRESS,
                ),
            )
            assert result.exception is None
            assert result.exit_code == 0
            mock_deploy.assert_called_once()
            mock_verify.assert_called_once()


@patch.object(ContractVerifier, "verify_deployed_contracts_in_filesystem")
def test_verify_script(mock_verify: MagicMock) -> None:
    """ Calling deploy verify command """
    with patch.object(Eth, "getBalance", return_value=1):
        runner = CliRunner()
        result = runner.invoke(verify, ["--rpc-provider", "rpc-provider"])
        assert result.exception is None
        assert result.exit_code == 0
        mock_verify.assert_called_once()


def test_verify_monitoring_service_deployment_with_wrong_first_constructor_arg(
    token_network_registry_contract: Contract,
) -> None:
    mock_token = MagicMock()
    mock_token.call.return_value = EMPTY_ADDRESS
    mock_monitoring_service = MagicMock()
    mock_monitoring_service.functions.token.return_value = mock_token
    with pytest.raises(RuntimeError):
        _verify_monitoring_service_deployment(
            monitoring_service=mock_monitoring_service,
            constructor_arguments=[FAKE_ADDRESS, 0, 1],
            token_address=EMPTY_ADDRESS,
            service_registry_address=FAKE_ADDRESS,
            user_deposit_address=FAKE_ADDRESS,
            token_network_registry_address=token_network_registry_contract.address,
        )


def test_verify_monitoring_service_deployment_with_wrong_onchain_token_address(
    token_network_registry_contract: Contract,
) -> None:
    mock_token = MagicMock()
    mock_token.call.return_value = EMPTY_ADDRESS
    mock_monitoring_service = MagicMock()
    mock_monitoring_service.functions.token.return_value = mock_token
    with pytest.raises(RuntimeError):
        _verify_monitoring_service_deployment(
            monitoring_service=mock_monitoring_service,
            constructor_arguments=[FAKE_ADDRESS, 0, 1],
            token_address=FAKE_ADDRESS,
            service_registry_address=EMPTY_ADDRESS,
            user_deposit_address=FAKE_ADDRESS,
            token_network_registry_address=token_network_registry_contract.address,
        )


def test_user_deposit_deployment_with_wrong_one_to_n_address() -> None:
    """ ContractVerifier.verify_user_deposit_deployment raises on a wrong OneToN address """
    token_addr = HexAddress(HexStr("0xDa12Dc74D2d0881749CCd9330ac4f0aecda5686a"))
    user_deposit_constructor_arguments = [token_addr, UINT256_MAX]
    wrong_one_to_n_address = FAKE_ADDRESS
    user_deposit_mock = MagicMock()
    mock_token_address = MagicMock()
    mock_token_address.call.return_value = token_addr
    user_deposit_mock.functions.token.return_value = mock_token_address

    with pytest.raises(RuntimeError):
        _verify_user_deposit_deployment(
            user_deposit=user_deposit_mock,
            constructor_arguments=user_deposit_constructor_arguments,
            token_address=token_addr,
            user_deposit_whole_balance_limit=UINT256_MAX,
            one_to_n_address=wrong_one_to_n_address,
            monitoring_service_address=HexAddress(
                HexStr("0xb7765972d78B6C97bB0a5a6b7529DC1fb64aA287")
            ),
        )
