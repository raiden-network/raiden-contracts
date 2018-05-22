import pytest


@pytest.fixture
def endpoint_registry_contract(deploy_tester_contract):
    """Deployed SecretRegistry contract"""
    return deploy_tester_contract('EndpointRegistry')
