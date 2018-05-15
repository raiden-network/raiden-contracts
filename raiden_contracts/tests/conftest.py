from raiden_libs.test.fixtures.web3 import *  # flake8: noqa
from raiden_libs.test.fixtures.address import *  # flake8: noqa

from .fixtures import *  # flake8: noqa

@pytest.fixture(scope='session')
def contract_deployer_address(faucet_address):
    return faucet_address
