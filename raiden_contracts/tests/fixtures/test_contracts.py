import pytest


@pytest.fixture()
def get_unlock_test(chain, create_contract):
    def get(arguments, transaction=None):
        UnlockTest = chain.provider.get_contract_factory('UnlockTest')
        contract = create_contract(UnlockTest, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def unlock_test(chain, get_unlock_test, custom_token, secret_registry):
    return get_unlock_test([
        custom_token.address,
        secret_registry.address,
        int(chain.web3.version.network)
    ])
