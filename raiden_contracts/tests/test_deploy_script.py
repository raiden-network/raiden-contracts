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
    verify_deployed_contracts,
)
from raiden_contracts.tests.fixtures.config import EMPTY_ADDRESS


def test_deploy_script(
    web3,
    contracts_manager,
    utils_contract,
    faucet_private_key,
    faucet_address,
    get_random_privkey,
):
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
