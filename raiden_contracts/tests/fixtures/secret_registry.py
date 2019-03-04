import pytest

from raiden_contracts.constants import CONTRACT_SECRET_REGISTRY


@pytest.fixture(scope='session')
def secret_registry_contract(deploy_tester_contract):
    """Deployed SecretRegistry contract"""
    return deploy_tester_contract(CONTRACT_SECRET_REGISTRY)
