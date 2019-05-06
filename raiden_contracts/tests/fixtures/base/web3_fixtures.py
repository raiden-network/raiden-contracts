import logging
from typing import Dict, Optional

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.contract import ContractFunction
from web3.providers.eth_tester import EthereumTesterProvider

from raiden_contracts.tests.utils.constants import (
    FAUCET_ADDRESS,
    FAUCET_ALLOWANCE,
    FAUCET_PRIVATE_KEY,
)

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def ethereum_tester(patch_genesis_gas_limit):  # pylint: disable=W0613
    """Returns an instance of an Ethereum tester"""
    return EthereumTester(PyEVMBackend())


@pytest.fixture(scope="session")
def patch_genesis_gas_limit():
    """Increases the block gas limit, to make the TokenNetworkRegistry contract deployable"""

    tmp_limit = 6 * 10 ** 6
    import eth_tester.backends.pyevm.main as pyevm_main

    pyevm_main.GENESIS_GAS_LIMIT = tmp_limit
    import eth.vm.forks.frontier.headers as headers

    headers.GENESIS_GAS_LIMIT = tmp_limit


@pytest.fixture(scope="session")
def web3(ethereum_tester,):
    """Returns an initialized Web3 instance"""
    provider = EthereumTesterProvider(ethereum_tester)
    web3 = Web3(provider)
    # Improve test speed by skipping the gas cost estimation.
    web3.eth.estimateGas = lambda txn: int(5.2e6)  # pylint: disable=E1101

    # add faucet account to tester
    ethereum_tester.add_account(FAUCET_PRIVATE_KEY)

    # make faucet rich
    ethereum_tester.send_transaction(
        {
            "from": ethereum_tester.get_accounts()[0],
            "to": FAUCET_ADDRESS,
            "gas": 21000,
            "value": FAUCET_ALLOWANCE,
        }
    )

    yield web3


@pytest.fixture(autouse=True)
def auto_revert_chain(web3: Web3):
    """Reverts the chain to its before the test run

    This reverts the side effects created during the test run, so that we can
    reuse the same chain and contract deployments for other tests.

    This is useful especially when using ethereum tester - its log filtering
    is very slow once enough events are present on-chain.
    """
    snapshot_id = web3.testing.snapshot()
    yield
    web3.testing.revert(snapshot_id)


def _call_and_transact(
    contract_function: ContractFunction, transaction_params: Optional[Dict] = None
) -> str:
    """ Executes contract_function.{call, transaction}(transaction_params) and returns txhash """
    # First 'call' might raise an exception
    contract_function.call(transaction_params)
    return contract_function.transact(transaction_params)


@pytest.fixture(scope="session", autouse=True)
def call_and_transact():
    ContractFunction.call_and_transact = _call_and_transact
