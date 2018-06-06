import pytest
from web3 import Web3
from web3.exceptions import ValidationError
from raiden_contracts.utils.config import E_SECRET_REVEALED
from raiden_contracts.utils.events import check_secret_revealed
from .fixtures.config import fake_bytes, raiden_contracts_version


def test_version(secret_registry_contract):
    assert (secret_registry_contract.functions.contract_version().call()[:2]
            == raiden_contracts_version[:2])


def test_register_secret_call(secret_registry_contract, event_handler):
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret().transact()
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret(3).transact()
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret(0).transact()
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret('').transact()
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret(fake_bytes(33)).transact()

    assert secret_registry_contract.functions.registerSecret(fake_bytes(32)).call() is False
    assert secret_registry_contract.functions.registerSecret(fake_bytes(10, '02')).call() is True
    assert secret_registry_contract.functions.registerSecret(fake_bytes(32, '02')).call() is True


def test_register_secret_return_value(secret_registry_contract, get_accounts):
    (A, B) = get_accounts(2)
    secret = b'secretsecretsecretsecretsecretse'

    # We use call here to make sure we would get the correct return value
    # even though this does not change the state
    assert secret_registry_contract.functions.registerSecret(secret).call({'from': A}) is True

    secret_registry_contract.functions.registerSecret(secret).transact({'from': A})

    # We use call here to get the return value
    assert secret_registry_contract.functions.registerSecret(secret).call({'from': A}) is False
    assert secret_registry_contract.functions.registerSecret(secret).call({'from': B}) is False


def test_register_secret(secret_registry_contract, get_accounts, get_block):
    (A, B) = get_accounts(2)
    secret = b'secretsecretsecretsecretsecretse'
    secret2 = b'secretsecretsecretsecretsecretss'
    secrethash = Web3.sha3(secret)

    assert secret_registry_contract.functions.secrethash_to_block(secrethash).call() == 0
    assert secret_registry_contract.functions.getSecretRevealBlockHeight(secrethash).call() == 0

    txn_hash = secret_registry_contract.functions.registerSecret(secret).transact({'from': A})

    assert (secret_registry_contract.functions.secrethash_to_block(secrethash).call()
            == get_block(txn_hash))
    assert secret_registry_contract.functions.getSecretRevealBlockHeight(
        secrethash
    ).call() == get_block(txn_hash)

    # A should be able to register any number of secrets
    secret_registry_contract.functions.registerSecret(secret2).transact({'from': A})


def test_events(secret_registry_contract, event_handler):
    secret = b'secretsecretsecretsecretsecretse'
    secrethash = Web3.sha3(secret)
    ev_handler = event_handler(secret_registry_contract)

    txn_hash = secret_registry_contract.functions.registerSecret(secret).transact()

    ev_handler.add(txn_hash, E_SECRET_REVEALED, check_secret_revealed(secrethash))
    ev_handler.check()
