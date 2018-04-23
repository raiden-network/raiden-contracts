import pytest
from web3 import Web3
from raiden_contracts.utils.config import E_SECRET_REVEALED
from raiden_contracts.utils.events import check_secret_revealed
from .fixtures.config import fake_hex, raiden_contracts_version


def test_version(secret_registry):
    assert secret_registry.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_register_secret_call(secret_registry):
    with pytest.raises(TypeError):
        secret_registry.transact().registerSecret()
    with pytest.raises(TypeError):
        secret_registry.transact().registerSecret(3)
    with pytest.raises(TypeError):
        secret_registry.transact().registerSecret(0)
    with pytest.raises(TypeError):
        secret_registry.transact().registerSecret('')
    with pytest.raises(TypeError):
        secret_registry.transact().registerSecret(fake_hex(33))

    # This works due to argument padding
    secret_registry.transact().registerSecret(fake_hex(10))

    secret_registry.transact().registerSecret(fake_hex(32))


def test_register_secret_return_value(secret_registry, get_accounts):
    (A, B) = get_accounts(2)
    secret = b'secretsecretsecretsecretsecretse'

    # We use call here to make sure we would get the correct return value
    # even though this does not change the state
    assert secret_registry.call({'from': A}).registerSecret(secret) is True

    secret_registry.transact({'from': A}).registerSecret(secret)

    # The secret cannot be registered again by anyone
    # FIXME Think about what happens if someone decides to use an already used
    # secret for a mediating transfer
    # We use call here to get the return value
    assert secret_registry.call({'from': A}).registerSecret(secret) is False
    assert secret_registry.call({'from': B}).registerSecret(secret) is False


def test_register_secret(secret_registry, get_accounts, get_block):
    (A, B) = get_accounts(2)
    secret = b'secretsecretsecretsecretsecretse'
    secret2 = b'secretsecretsecretsecretsecretss'
    secrethash = Web3.sha3(secret)

    assert secret_registry.call().secrethash_to_block(secrethash) == 0
    assert secret_registry.call().getSecretRevealBlockHeight(secrethash) == 0

    txn_hash = secret_registry.transact({'from': A}).registerSecret(secret)

    assert secret_registry.call().secrethash_to_block(secrethash) == get_block(txn_hash)
    assert secret_registry.call().getSecretRevealBlockHeight(secrethash) == get_block(txn_hash)

    # A should be able to register any number of secrets
    secret_registry.transact({'from': A}).registerSecret(secret2)


def test_events(secret_registry, event_handler):
    secret = b'secretsecretsecretsecretsecretse'
    secrethash = Web3.sha3(secret)
    ev_handler = event_handler(secret_registry)

    txn_hash = secret_registry.transact().registerSecret(secret)

    ev_handler.add(txn_hash, E_SECRET_REVEALED, check_secret_revealed(secrethash))
    ev_handler.check()
