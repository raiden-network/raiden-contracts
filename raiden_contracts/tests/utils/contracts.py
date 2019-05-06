from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_TOKEN_NETWORK
from raiden_contracts.tests.utils.constants import FAUCET_ALLOWANCE
from raiden_contracts.utils.signature import private_key_to_address


def get_web3(eth_tester, deployer_key):
    """Returns an initialized Web3 instance"""
    provider = EthereumTesterProvider(eth_tester)
    web3 = Web3(provider)

    # add faucet account to tester
    eth_tester.add_account(deployer_key.to_hex())

    # make faucet rich
    eth_tester.send_transaction(
        {
            "from": eth_tester.get_accounts()[0],
            "to": private_key_to_address(deployer_key.to_hex()),
            "gas": 21000,
            "value": FAUCET_ALLOWANCE,
        }
    )

    return web3


def deploy_contract(web3, contracts_manager, contract_name, deployer_key, args=None):
    deployer_address = private_key_to_address(deployer_key.to_hex())
    json_contract = contracts_manager.get_contract(contract_name)
    contract = web3.eth.contract(abi=json_contract["abi"], bytecode=json_contract["bin"])
    tx_hash = contract.constructor(*args).call_and_transact({"from": deployer_address})
    contract_address = web3.eth.getTransactionReceipt(tx_hash).contractAddress

    return contract(contract_address)


def deploy_custom_token(web3, deployer_key):
    return deploy_contract(
        web3, CONTRACT_CUSTOM_TOKEN, deployer_key, [], (10 ** 26, 18, CONTRACT_CUSTOM_TOKEN, "TKN")
    )


def get_token_network(web3, address, contracts_manager):
    json_contract = contracts_manager.get_contract(CONTRACT_TOKEN_NETWORK)

    return web3.eth.contract(abi=json_contract["abi"], address=address)
