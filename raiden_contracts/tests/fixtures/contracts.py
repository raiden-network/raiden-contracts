import pytest
import logging
from web3.utils.events import get_event_data
from eth_utils import is_address

from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    EVENT_TOKEN_NETWORK_CREATED,
)

log = logging.getLogger(__name__)


@pytest.fixture
def contract_deployer_address(faucet_address) -> str:
    """Reimplement this - fixture should return an address of the account
    that has enough eth to deploy the contracts."""
    raise NotImplementedError(
        'Address of a deployer account must be overriden.',
    )


@pytest.fixture
def deploy_tester_contract(
        web3,
        contracts_manager,
        deploy_contract,
        contract_deployer_address,
        wait_for_transaction,
        get_random_address,
):
    """Returns a function that can be used to deploy a named contract,
    using conract manager to compile the bytecode and get the ABI"""
    def f(contract_name, libs=None, args=None):
        json_contract = contracts_manager.get_contract(contract_name)
        contract = deploy_contract(
            web3,
            contract_deployer_address,
            json_contract['abi'],
            json_contract['bin'],
            args,
        )
        return contract
    return f


@pytest.fixture
def deploy_tester_contract_txhash(
        web3,
        contracts_manager,
        deploy_contract_txhash,
        contract_deployer_address,
        wait_for_transaction,
        get_random_address,
):
    """Returns a function that can be used to deploy a named contract,
    but returning txhash only"""
    def f(contract_name, libs=None, args=None):
        json_contract = contracts_manager.get_contract(contract_name)
        txhash = deploy_contract_txhash(
            web3,
            contract_deployer_address,
            json_contract['abi'],
            json_contract['bin'],
            args,
        )
        return txhash
    return f


@pytest.fixture
def utils_contract(deploy_tester_contract):
    """Deployed Utils contract"""
    return deploy_tester_contract('Utils')


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
