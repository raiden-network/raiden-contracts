import pytest
from web3.utils.events import get_event_data
from eth_utils import is_address
from raiden_contracts.constants import (
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_HUMAN_STANDARD_TOKEN,
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_CUSTOM_TOKEN_NO_DECIMALS,
    EVENT_TOKEN_NETWORK_CREATED,
)
from .utils import *  # flake8: noqa

token_args = [
    (10 ** 26, 18, CONTRACT_CUSTOM_TOKEN, 'TKN')
]

token_args_7_decimals = [
    (10 ** 26, 7, CONTRACT_CUSTOM_TOKEN, 'TD6')
]

token_args_no_decimals = [
    (10 ** 26, CONTRACT_CUSTOM_TOKEN_NO_DECIMALS, 'TNO')
]


@pytest.fixture(params=token_args)
def custom_token_params(request):
    return request.param


@pytest.fixture(params=token_args_7_decimals)
def custom_token_7_decimals_params(request):
    return request.param


@pytest.fixture(params=token_args_no_decimals)
def custom_token_no_decimals_params(request):
    return request.param


@pytest.fixture()
def custom_token(deploy_tester_contract, custom_token_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        CONTRACT_CUSTOM_TOKEN,
        [],
        custom_token_params
    )[0]


@pytest.fixture()
def custom_token_7_decimals(deploy_tester_contract, custom_token_7_decimals_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        CONTRACT_CUSTOM_TOKEN,
        [],
        custom_token_7_decimals_params
    )[0]


@pytest.fixture()
def custom_token_no_decimals(deploy_tester_contract, custom_token_no_decimals_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        CONTRACT_CUSTOM_TOKEN_NO_DECIMALS,
        [],
        custom_token_no_decimals_params
    )[0]


@pytest.fixture()
def human_standard_token(deploy_token_contract, custom_token_params):
    """Deploy HumanStandardToken contract"""
    return deploy_token_contract(*custom_token_params)


@pytest.fixture
def deploy_token_contract(deploy_tester_contract):
    """Returns a function that deploys a generic HumanStandardToken contract"""
    def f(initial_amount: int, decimals: int, token_name: str, token_symbol: str):
        assert initial_amount > 0
        assert decimals > 0
        return deploy_tester_contract(
            CONTRACT_HUMAN_STANDARD_TOKEN,
            [],
            [initial_amount, decimals, token_name, token_symbol]
        )[0]

    return f


@pytest.fixture
def standard_token_contract(custom_token):
    """Deployed CustomToken contract"""
    return custom_token


@pytest.fixture
def standard_token_network_contract(
        web3,
        contracts_manager,
        wait_for_transaction,
        token_network_registry_contract,
        standard_token_contract,
        contract_deployer_address,
):
    """Return instance of a deployed TokenNetwork for HumanStandardToken."""
    txid = token_network_registry_contract.functions.createERC20TokenNetwork(
        standard_token_contract.address,
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
