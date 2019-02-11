import pytest
from eth_utils import ValidationError
from copy import deepcopy

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
)
from raiden_contracts.deploy.__main__ import (
    ContractDeployer,
    deploy_raiden_contracts,
    deploy_service_contracts,
    deploy_token_contract,
    register_token_network,
    verify_deployed_contracts,
    verify_deployed_service_contracts,
)
from raiden_contracts.tests.utils.constants import EMPTY_ADDRESS
from raiden_contracts.utils.type_aliases import T_Address


def test_deploy_script_raiden(
    web3,
    faucet_private_key,
    get_random_privkey,
):
    """ Run raiden contracts deployment function and tamper with deployed_contracts_info

    This checks if deploy_raiden_contracts() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    This also tampers with deployed_contracts_info to make sure an error is raised in
    verify_deployed_contracts()
    """
    # normal deployment
    gas_limit = 5900000
    deployer = ContractDeployer(
        web3=web3,
        private_key=faucet_private_key,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    deployed_contracts_info = deploy_raiden_contracts(deployer)

    verify_deployed_contracts(deployer.web3, deployer.contract_manager, deployed_contracts_info)

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts_version'] = '0.0.0'
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['chain_id'] = 0
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][
        CONTRACT_ENDPOINT_REGISTRY
    ]['address'] = EMPTY_ADDRESS
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_SECRET_REGISTRY]['address'] = EMPTY_ADDRESS
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][
        CONTRACT_TOKEN_NETWORK_REGISTRY
    ]['address'] = EMPTY_ADDRESS
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_ENDPOINT_REGISTRY]['block_number'] = 0
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_SECRET_REGISTRY]['block_number'] = 0
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info_fail,
        )

    deployed_contracts_info_fail = deepcopy(deployed_contracts_info)
    deployed_contracts_info_fail['contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY]['block_number'] = 0
    with pytest.raises(AssertionError):
        verify_deployed_contracts(
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
        deploy_raiden_contracts(deployer)


def test_deploy_script_token(
    web3,
    faucet_private_key,
    get_random_privkey,
):
    """ Run test token deployment function used in the deployment script

    This checks if deploy_token_contract() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    """
    # normal deployment
    gas_limit = 5900000
    token_type = 'CustomToken'
    deployer = ContractDeployer(
        web3=web3,
        private_key=faucet_private_key,
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


def test_deploy_script_register(
    web3,
    faucet_private_key,
    get_random_privkey,
):
    """ Run token register function used in the deployment script

    This checks if register_token_network() works correctly in the happy case,
    to make sure no code dependencies have been changed, affecting the deployment script.
    This does not check however that the cli command works correctly.
    """
    # normal deployment
    gas_limit = 5900000
    token_type = 'CustomToken'
    deployer = ContractDeployer(
        web3=web3,
        private_key=faucet_private_key,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    deployed_contracts_raiden = deploy_raiden_contracts(deployer)
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
        web3,
        deployer.owner,
        token_registry_abi,
        token_registry_address,
        token_address,
    )
    assert token_network_address is not None
    assert isinstance(token_network_address, T_Address)


def test_deploy_script_service(
        web3,
        faucet_private_key,
        get_random_privkey,
):
    """ Run deploy_service_contracts() used in the deployment script

    This checks if deploy_service_contracts() works correctly in the happy case.
    """
    gas_limit = 5900000
    deployer = ContractDeployer(
        web3=web3,
        private_key=faucet_private_key,
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )

    token_type = 'CustomToken'
    deployed_token = deploy_token_contract(
        deployer,
        token_supply=10000000,
        token_decimals=18,
        token_name='TestToken',
        token_symbol='TTT',
        token_type=token_type,
    )
    token_address = deployed_token[token_type]
    assert isinstance(token_address, T_Address)

    deployed_service_contracts = deploy_service_contracts(deployer, token_address)
    verify_deployed_service_contracts(
        deployer.web3,
        deployer.contract_manager,
        token_address,
        deployed_service_contracts,
    )
