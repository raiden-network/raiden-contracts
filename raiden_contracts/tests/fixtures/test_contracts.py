import pytest


@pytest.fixture()
def get_token_network_test(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            'TokenNetworkInternalsTest',
            {},
            arguments
        )
    return get


@pytest.fixture()
def token_network_test(web3, get_token_network_test, custom_token, secret_registry_contract):
    return get_token_network_test([
        custom_token.address,
        secret_registry_contract.address,
        int(web3.version.network)
    ])
