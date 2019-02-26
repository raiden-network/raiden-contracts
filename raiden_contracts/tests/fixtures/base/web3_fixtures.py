import logging
import pytest

from eth_utils import denoms
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from raiden_contracts.tests.utils.constants import FAUCET_PRIVATE_KEY, FAUCET_ADDRESS

DEFAULT_TIMEOUT = 5
DEFAULT_RETRY_INTERVAL = 3
FAUCET_ALLOWANCE = 100 * denoms.ether  # pylint: disable=E1101
INITIAL_TOKEN_SUPPLY = 200000000000

log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def ethereum_tester():
    """Returns an instance of an Ethereum tester"""
    return EthereumTester(PyEVMBackend())


@pytest.fixture(scope='session')
def patch_genesis_gas_limit():
    """Increases the block gas limit, to make the TokenNetworkRegistry contract deployable"""
    import eth_tester.backends.pyevm.main as pyevm_main
    original_gas_limit = pyevm_main.GENESIS_GAS_LIMIT
    pyevm_main.GENESIS_GAS_LIMIT = 6 * 10 ** 6

    yield

    pyevm_main.GENESIS_GAS_LIMIT = original_gas_limit


@pytest.fixture(scope='session')
def web3(
        patch_genesis_gas_limit,
        ethereum_tester,
):
    """Returns an initialized Web3 instance"""
    provider = EthereumTesterProvider(ethereum_tester)
    web3 = Web3(provider)

    # add faucet account to tester
    ethereum_tester.add_account(FAUCET_PRIVATE_KEY)

    # make faucet rich
    ethereum_tester.send_transaction({
        'from': ethereum_tester.get_accounts()[0],
        'to': FAUCET_ADDRESS,
        'gas': 21000,
        'value': FAUCET_ALLOWANCE,
    })

    yield web3


@pytest.fixture
def revert_chain(web3: Web3):
    """Reverts chain to its initial state.
    If this fixture is used, the chain will revert on each test teardown.

    This is useful especially when using ethereum tester - its log filtering
    is very slow once enough events are present on-chain.

    Note that `deploy_contract` fixture uses `revert_chain` by default.
    """
    snapshot_id = web3.testing.snapshot()
    yield
    web3.testing.revert(snapshot_id)
