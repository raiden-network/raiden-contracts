from copy import deepcopy

import pytest
from click import BadParameter
from eth_utils import ValidationError, to_checksum_address

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
)
from raiden_contracts.contract_manager import contract_version_string
from raiden_contracts.deploy.__main__ import (
    ContractDeployer,
    deploy_raiden_contracts,
    deploy_service_contracts,
    deploy_token_contract,
    register_token_network,
    validate_address,
    verify_deployment_data,
    verify_service_contracts_deployment_data,
)
from raiden_contracts.tests.utils import get_random_privkey
from raiden_contracts.tests.utils.constants import (
    CONTRACT_DEPLOYER_ADDRESS,
    EMPTY_ADDRESS,
    FAUCET_PRIVATE_KEY,
)
from raiden_contracts.utils.type_aliases import T_Address


@pytest.mark.slow
def test_deploy_script_raiden(
        web3,
):
    """ Run raiden contracts deployment function and tamper with deployed_contracts_info

    This checks if deploy_raiden_contracts() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    This also tampers with deployed_contracts_info to make sure an error is raised in
    verify_deployed_contracts()
    """
    # normal deployment
    gas_limit = 5860000
    deployer = ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    deployed_contracts_info = deploy_raiden_contracts(deployer, 1)

    verify_deployment_data(
        web3=deployer.web3,
        contract_manager=deployer.contract_manager,
        deployment_data=deployed_contracts_info,
    )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts_version'] = '0.0.0'
    with pytest.raises(AssertionError):
        verify_deployment_data(
            web3=deployer.web3,
            contract_manager=deployer.contract_manager,
            deployment_data=deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['chain_id'] = 0
    with pytest.raises(AssertionError):
        verify_deployment_data(
            web3=deployer.web3,
            contract_manager=deployer.contract_manager,
            deployment_data=deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][
        CONTRACT_ENDPOINT_REGISTRY
    ]['address'] = EMPTY_ADDRESS
    with pytest.raises(AssertionError):
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_SECRET_REGISTRY]['address'] = EMPTY_ADDRESS
    with pytest.raises(AssertionError):
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][
        CONTRACT_TOKEN_NETWORK_REGISTRY
    ]['address'] = EMPTY_ADDRESS
    with pytest.raises(AssertionError):
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_ENDPOINT_REGISTRY]['block_number'] = 0
    with pytest.raises(AssertionError):
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_SECRET_REGISTRY]['block_number'] = 0
    with pytest.raises(AssertionError):
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY]['block_number'] = 0
    with pytest.raises(AssertionError):
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    # check that it fails if sender has no eth
    deployer = ContractDeployer(
        web3=web3,
        private_key=get_random_privkey(),
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )
    with pytest.raises(ValidationError):
        deploy_raiden_contracts(deployer, 1)


def test_deploy_script_token(
        web3,
):
    """ Run test token deployment function used in the deployment script

    This checks if deploy_token_contract() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    """
    # normal deployment
    gas_limit = 5860000
    token_type = 'CustomToken'
    deployer = ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    deployed_token = deploy_token_contract(
        deployer,
        token_supply=10000000,
        token_decimals=18,
        token_name='TestToken',
        token_symbol='TTT',
        token_type=token_type,
    )

    assert deployed_token[token_type] is not None
    assert isinstance(deployed_token[token_type], T_Address)

    # check that it fails if sender has no eth
    deployer = ContractDeployer(
        web3=web3,
        private_key=get_random_privkey(),
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )
    with pytest.raises(ValidationError):
        deploy_token_contract(
            deployer,
            token_supply=10000000,
            token_decimals=18,
            token_name='TestToken',
            token_symbol='TTT',
            token_type='CustomToken',
        )


@pytest.mark.slow
def test_deploy_script_register(
        web3,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ Run token register function used in the deployment script

    This checks if register_token_network() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    """
    # normal deployment
    gas_limit = 5860000
    token_type = 'CustomToken'
    deployer = ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    deployed_contracts_raiden = deploy_raiden_contracts(
        deployer=deployer,
        max_num_of_token_networks=1,
    )
    deployed_token = deploy_token_contract(
        deployer,
        token_supply=10000000,
        token_decimals=18,
        token_name='TestToken',
        token_symbol='TTT',
        token_type=token_type,
    )
    token_address = deployed_token[token_type]
    token_registry_abi = deployer.contract_manager.get_contract_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
    )
    token_registry_address = deployed_contracts_raiden['contracts'][
        CONTRACT_TOKEN_NETWORK_REGISTRY
    ]['address']
    token_network_address = register_token_network(
        web3=web3,
        caller=deployer.owner,
        token_registry_abi=token_registry_abi,
        token_registry_address=token_registry_address,
        token_registry_version=contract_version_string(version=None),
        token_address=token_address,
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
    )
    assert token_network_address is not None
    assert isinstance(token_network_address, T_Address)


@pytest.mark.slow
def test_deploy_script_service(
        web3,
):
    """ Run deploy_service_contracts() used in the deployment script

    This checks if deploy_service_contracts() works correctly in the happy case.
    """
    gas_limit = 5860000
    deployer = ContractDeployer(
        web3=web3,
        private_key=FAUCET_PRIVATE_KEY,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    token_type = 'CustomToken'
    token_supply = 10000000
    deployed_token = deploy_token_contract(
        deployer,
        token_supply=token_supply,
        token_decimals=18,
        token_name='TestToken',
        token_symbol='TTT',
        token_type=token_type,
    )
    token_address = deployed_token[token_type]
    assert isinstance(token_address, T_Address)
    deposit_limit = token_supply // 2

    deployed_service_contracts = deploy_service_contracts(
        deployer=deployer,
        token_address=token_address,
        user_deposit_whole_balance_limit=deposit_limit,
    )
    verify_service_contracts_deployment_data(
        web3=deployer.web3,
        contract_manager=deployer.contract_manager,
        token_address=token_address,
        user_deposit_whole_balance_limit=deposit_limit,
        deployment_data=deployed_service_contracts,
    )

    deployed_info_fail = deepcopy(deployed_service_contracts)
    deployed_info_fail['contracts_version'] = '0.0.0'
    with pytest.raises(AssertionError):
        verify_service_contracts_deployment_data(
            web3=deployer.web3,
            contract_manager=deployer.contract_manager,
            token_address=token_address,
            user_deposit_whole_balance_limit=deposit_limit,
            deployment_data=deployed_info_fail,
        )

    def test_missing_deployment(contract_name):
        deployed_info_fail = deepcopy(deployed_service_contracts)
        deployed_info_fail['contracts'][
            contract_name
        ]['address'] = EMPTY_ADDRESS
        with pytest.raises(AssertionError):
            verify_service_contracts_deployment_data(
                web3=deployer.web3,
                contract_manager=deployer.contract_manager,
                token_address=token_address,
                user_deposit_whole_balance_limit=deposit_limit,
                deployment_data=deployed_info_fail,
            )

    for contract_name in [
            CONTRACT_SERVICE_REGISTRY,
            CONTRACT_MONITORING_SERVICE,
            CONTRACT_ONE_TO_N,
            CONTRACT_USER_DEPOSIT,
    ]:
        test_missing_deployment(contract_name)


def test_validate_address_on_none():
    """ validate_address(x, y, None) should return None """
    assert validate_address(None, None, None) is None


def test_validate_address_empty_string():
    """ validate_address(x, y, '') should return None """
    assert validate_address(None, None, '') is None


def test_validate_address_not_an_address():
    """ validate_address(x, y, 'not an address') should raise click.BadParameter """
    with pytest.raises(BadParameter):
        validate_address(None, None, 'not an address')


def test_validate_address_happy_path():
    """ validate_address(x, y, address) should return the same address checksumed """
    address = CONTRACT_DEPLOYER_ADDRESS
    assert validate_address(None, None, address) == to_checksum_address(address)
