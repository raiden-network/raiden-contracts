import pytest


@pytest.fixture()
def secret_registry(secret_registry_contract):
    return secret_registry_contract
