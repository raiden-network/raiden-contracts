import pytest
from web3 import Web3
from web3.exceptions import ValidationError
from raiden_contracts.utils.config import E_SECRET_REVEALED
from raiden_contracts.utils.events import check_secret_revealed
from .fixtures.config import fake_bytes, raiden_contracts_version


def test_version(secret_registry_contract):
    assert secret_registry_contract.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_register_secret_call(secret_registry_contract, event_handler):
    with pytest.raises(ValidationError):
        secret_registry_contract.transact().registerSecret()
    with pytest.raises(ValidationError):
        secret_registry_contract.transact().registerSecret(3)
    with pytest.raises(ValidationError):
        secret_registry_contract.transact().registerSecret(0)
    with pytest.raises(ValidationError):
        secret_registry_contract.transact().registerSecret('')
    with pytest.raises(ValidationError):
        secret_registry_contract.transact().registerSecret(fake_bytes(33))

    assert secret_registry_contract.call().registerSecret(fake_bytes(32)) is False
    assert secret_registry_contract.call().registerSecret(fake_bytes(10, '02')) is True
    assert secret_registry_contract.call().registerSecret(fake_bytes(32, '02')) is True


def test_register_secret_return_value(secret_registry_contract, get_accounts):
    (A, B) = get_accounts(2)
    secret = b'secretsecretsecretsecretsecretse'

    # We use call here to make sure we would get the correct return value
    # even though this does not change the state
    assert secret_registry_contract.call({'from': A}).registerSecret(secret) is True

    secret_registry_contract.transact({'from': A}).registerSecret(secret)

    # We use call here to get the return value
    assert secret_registry_contract.call({'from': A}).registerSecret(secret) is False
    assert secret_registry_contract.call({'from': B}).registerSecret(secret) is False


def test_register_secret(secret_registry_contract, get_accounts, get_block):
    (A, B) = get_accounts(2)
    secret = b'secretsecretsecretsecretsecretse'
    secret2 = b'secretsecretsecretsecretsecretss'
    secrethash = Web3.sha3(secret)

    assert secret_registry_contract.call().secrethash_to_block(secrethash) == 0
    assert secret_registry_contract.call().getSecretRevealBlockHeight(secrethash) == 0

    txn_hash = secret_registry_contract.transact({'from': A}).registerSecret(secret)

    assert secret_registry_contract.call().secrethash_to_block(secrethash) == get_block(txn_hash)
    assert secret_registry_contract.call().getSecretRevealBlockHeight(
        secrethash
    ) == get_block(txn_hash)

    # A should be able to register any number of secrets
    secret_registry_contract.transact({'from': A}).registerSecret(secret2)


def test_events(secret_registry_contract, event_handler):
    secret = b'secretsecretsecretsecretsecretse'
    secrethash = Web3.sha3(secret)
    ev_handler = event_handler(secret_registry_contract)

    txn_hash = secret_registry_contract.transact().registerSecret(secret)

    ev_handler.add(txn_hash, E_SECRET_REVEALED, check_secret_revealed(secrethash))
    ev_handler.check()
