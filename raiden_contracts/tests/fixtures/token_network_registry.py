import pytest
from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    LIBRARY_TOKEN_NETWORK_UTILS,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)
from web3.contract import get_event_data
from eth_utils import is_address
from raiden_contracts.contract_manager import CONTRACTS_SOURCE_DIRS


@pytest.fixture
def token_network_utils_library(deploy_tester_contract, web3):
    """Deployed TokenNetworkUtils library"""
    return deploy_tester_contract(LIBRARY_TOKEN_NETWORK_UTILS)[0]


@pytest.fixture
def token_network_libs(token_network_utils_library):
    """Deployed TokenNetworkUtils library"""
    # FIXME
    # libraries should look lile: {'TokenNetworkUtils': token_network_utils_library.address}
    # But solc assigns only 36 characters to the library name
    # In our case, with remappings, the library name contains the full path to the library file
    # Therefore, we get the same name for all libraries, containing path of the file path
    libs = {}
    libs[str(CONTRACTS_SOURCE_DIRS['raiden'])[:36]] = token_network_utils_library.address
    return libs


@pytest.fixture()
def get_token_network_registry(deploy_tester_contract, token_network_libs):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            CONTRACT_TOKEN_NETWORK_REGISTRY,
            token_network_libs,
            arguments,
        )[0]
    return get


@pytest.fixture
def token_network_registry_contract(
        deploy_tester_contract,
        token_network_libs,
        secret_registry_contract,
        web3,
):
    """Deployed TokenNetworkRegistry contract"""
    return deploy_tester_contract(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        token_network_libs,
        [
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )[0]


@pytest.fixture
def token_network_registry_address(token_network_registry_contract):
    """Address of TokenNetworkRegistry contract"""
    return token_network_registry_contract.address


@pytest.fixture
def add_and_register_token(
        web3,
        wait_for_transaction,
        token_network_registry_contract,
        deploy_token_contract,
        contract_deployer_address,
        contracts_manager,
):
    """Deploy a token and register it in TokenNetworkRegistry"""
    def f(initial_amount: int, decimals: int, token_name: str, token_symbol: str):
        token_contract = deploy_token_contract(initial_amount, decimals, token_name, token_symbol)
        txid = token_network_registry_contract.functions.createERC20TokenNetwork(
            token_contract.address,
        ).transact({'from': contract_deployer_address})
        tx_receipt = wait_for_transaction(txid)
        assert len(tx_receipt['logs']) == 1
        event_abi = contracts_manager.get_event_abi(
            CONTRACT_TOKEN_NETWORK_REGISTRY,
            EVENT_TOKEN_NETWORK_CREATED,
        )
        decoded_event = get_event_data(event_abi, tx_receipt['logs'][0])
        assert decoded_event is not None
        assert is_address(decoded_event['args']['token_address'])
        assert is_address(decoded_event['args']['token_network_address'])
        token_network_address = decoded_event['args']['token_network_address']
        token_network_abi = contracts_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK)
        return web3.eth.contract(abi=token_network_abi, address=token_network_address)

    return f
