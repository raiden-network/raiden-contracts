import pytest


@pytest.fixture()
def get_unlock_test(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            'UnlockTest',
            {},
            arguments
        )
    return get


@pytest.fixture()
def unlock_test(web3, get_unlock_test, custom_token, secret_registry):
    return get_unlock_test([
        custom_token.address,
        secret_registry.address,
        int(web3.version.network)
    ])
