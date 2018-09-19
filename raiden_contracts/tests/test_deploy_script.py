import pytest
from eth_utils import ValidationError

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
)
from raiden_contracts.deploy.__main__ import ContractDeployer, deploy_raiden_contracts


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
    res = deploy_raiden_contracts(
        deployer,
    )
    assert CONTRACT_ENDPOINT_REGISTRY in res
    assert CONTRACT_TOKEN_NETWORK_REGISTRY in res
    assert CONTRACT_SECRET_REGISTRY in res

    # check that it fails if sender has no eth
    deployer = ContractDeployer(
        web3=web3,
        private_key=get_random_privkey(),
        gas_limit=gas_limit,
        gas_price=1,
        wait=10,
    )
    with pytest.raises(ValidationError):
        deploy_raiden_contracts(
            deployer,
        )
