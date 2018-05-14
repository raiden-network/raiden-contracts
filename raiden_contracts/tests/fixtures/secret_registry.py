import pytest


@pytest.fixture
def secret_registry_contract(deploy_tester_contract):
    """Deployed SecretRegistry contract"""
    return deploy_tester_contract('SecretRegistry')
