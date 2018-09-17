import pytest
import logging
from solc import link_code


log = logging.getLogger(__name__)


@pytest.fixture
def contract_deployer_address(faucet_address) -> str:
    """Reimplement this - fixture should return an address of the account
    that has enough eth to deploy the contracts."""
    raise NotImplementedError(
        'Address of a deployer account must be overriden.',
    )


@pytest.fixture
def deploy_contract_txhash(revert_chain):
    """Returns a function that deploys a compiled contract, returning a txhash"""
    def fn(
            web3,
            deployer_address,
            abi,
            bytecode,
            args,
            bytecode_runtime=None,
    ):
        if args is None:
            args = []
        if bytecode_runtime is not None:
            contract = web3.eth.contract(
                abi=abi,
                bytecode=bytecode,
                bytecode_runtime=bytecode_runtime,
            )
        else:
            contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        web3.testing.mine(3)
        return contract.constructor(*args).transact({'from': deployer_address})
    return fn


@pytest.fixture
def deploy_contract(revert_chain, deploy_contract_txhash):
    """Returns a function that deploys a compiled contract"""
    def fn(
            web3,
            deployer_address,
            abi,
            bytecode,
            args,
            bytecode_runtime,
    ):
        txhash = deploy_contract_txhash(
            web3,
            deployer_address,
            abi,
            bytecode,
            args,
            bytecode_runtime,
        )

        contract = web3.eth.contract(abi=abi, bytecode=bytecode)

        contract_address = web3.eth.getTransactionReceipt(txhash).contractAddress
        web3.testing.mine(1)

        return contract(contract_address), txhash
    return fn


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
    using contract manager to compile the bytecode and get the ABI"""
    def f(contract_name, libs=None, args=None):
        json_contract = contracts_manager.get_contract(contract_name)

        if isinstance(libs, dict):
            json_contract['bin'] = link_code(json_contract['bin'], libs)
            json_contract['bin-runtime'] = link_code(json_contract['bin-runtime'], libs)

        return deploy_contract(
            web3,
            contract_deployer_address,
            json_contract['abi'],
            json_contract['bin'],
            args,
            bytecode_runtime=json_contract['bin-runtime'],
        )
    return f
