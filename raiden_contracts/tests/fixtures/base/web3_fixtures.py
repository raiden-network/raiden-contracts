import logging
from typing import Generator

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from raiden_contracts.tests.utils.constants import (
    FAUCET_ADDRESS,
    FAUCET_ALLOWANCE,
    FAUCET_PRIVATE_KEY,
)

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def ethereum_tester(patch_genesis_gas_limit: None) -> EthereumTester:  # pylint: disable=W0613
    """Returns an instance of an Ethereum tester"""
    return EthereumTester(PyEVMBackend())


@pytest.fixture(scope="session")
def patch_genesis_gas_limit() -> None:
    """Increases the block gas limit, to make the TokenNetworkRegistry contract deployable"""

    tmp_limit = 6 * 10 ** 6
    import eth_tester.backends.pyevm.main as pyevm_main

    pyevm_main.GENESIS_GAS_LIMIT = tmp_limit
    import eth.vm.forks.frontier.headers as headers

    headers.GENESIS_GAS_LIMIT = tmp_limit


@pytest.fixture(scope="session")
def web3(ethereum_tester: EthereumTester) -> Web3:
    """Returns an initialized Web3 instance"""
    provider = EthereumTesterProvider(ethereum_tester)
    web3 = Web3(provider)
    # Improve test speed by skipping the gas cost estimation.
    web3.eth.estimateGas = lambda txn: int(5.2e6)  # pylint: disable=E1101

    # add faucet account to tester
    ethereum_tester.add_account(FAUCET_PRIVATE_KEY.hex())

    # make faucet rich
    ethereum_tester.send_transaction(
        {
            "from": ethereum_tester.get_accounts()[0],
            "to": FAUCET_ADDRESS,
            "gas": 21000,
            "value": FAUCET_ALLOWANCE,
        }
    )

    # Enable strict type checks
    web3.enable_strict_bytes_type_checking()

    return web3


@pytest.fixture(autouse=True)
def auto_revert_chain(web3: Web3) -> Generator:
    """Reverts the chain to its before the test run

    This reverts the side effects created during the test run, so that we can
    reuse the same chain and contract deployments for other tests.

    This is useful especially when using ethereum tester - its log filtering
    is very slow once enough events are present on-chain.
    """
    snapshot_id = web3.testing.snapshot()  # type: ignore
    yield
    web3.testing.revert(snapshot_id)  # type: ignore
