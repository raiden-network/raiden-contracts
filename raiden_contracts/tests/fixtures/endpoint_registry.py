import pytest

from raiden_contracts.constants import CONTRACT_ENDPOINT_REGISTRY


@pytest.fixture
def endpoint_registry_contract(deploy_tester_contract):
    """Deployed SecretRegistry contract"""
    return deploy_tester_contract(CONTRACT_ENDPOINT_REGISTRY)
