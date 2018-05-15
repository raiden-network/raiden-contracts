import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK, C_TOKEN_NETWORK_REGISTRY
from web3.contract import get_event_data


@pytest.fixture
def get_token_network(web3, deploy_tester_contract):
    """Deploy a token network as a separate contract (registry is not used)"""
    def get(arguments):
        return deploy_tester_contract(
            C_TOKEN_NETWORK,
            {},
            arguments
        )
    return get


@pytest.fixture
def register_token_network(
    owner,
    web3,
    token_network_registry_contract,
    contracts_manager
):
    """Returns a function that uses token_network_registry fixture to register
    and deploy a new token network"""
    def get(token_address):
        tx_hash = token_network_registry_contract.transact(
            {'from': owner}
        ).createERC20TokenNetwork(
            token_address
        )
        tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
        event_abi = contracts_manager.get_event_abi(
            C_TOKEN_NETWORK_REGISTRY,
            'TokenNetworkCreated'
        )
        event_data = get_event_data(event_abi, tx_receipt['logs'][0])
        contract_address = event_data['args']['token_network_address']
        contract = web3.eth.contract(
            abi=contracts_manager.get_contract_abi(C_TOKEN_NETWORK),
            address=contract_address
        )
        return contract
    return get


@pytest.fixture
def token_network(
    register_token_network,
    custom_token,
):
    """Register a new token network for a custom token"""
    return register_token_network(custom_token.address)


@pytest.fixture
def token_network_contract(
        deploy_tester_contract,
        secret_registry_contract,
        standard_token_contract
):
    network_id = int(secret_registry_contract.web3.version.network)
    return deploy_tester_contract(
        'TokenNetwork',
        {
            'Token': standard_token_contract.address.encode(),
            'SecretRegistry': secret_registry_contract.address.encode()
        },
        [standard_token_contract.address, secret_registry_contract.address, network_id]
    )


@pytest.fixture()
def token_network_external(web3, get_token_network, custom_token, secret_registry_contract):
    return get_token_network([
        custom_token.address,
        secret_registry_contract.address,
        int(web3.version.network)
    ])
