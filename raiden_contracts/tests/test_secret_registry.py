from hashlib import sha256

import pytest
from web3.exceptions import ValidationError

from raiden_contracts.constants import CONTRACTS_VERSION, EVENT_SECRET_REVEALED
from raiden_contracts.tests.utils.mock import fake_bytes
from raiden_contracts.utils.events import check_secret_revealed, check_secrets_revealed


def test_version(secret_registry_contract):
    """ Test the return value of contract_version() """
    version = secret_registry_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION


def test_register_secret_call(secret_registry_contract):
    """ Test the registrable and not registrable secrets """
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret()
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret(3)
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret(0)
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret("")
    with pytest.raises(ValidationError):
        secret_registry_contract.functions.registerSecret(fake_bytes(33))

    # For interoperability with other SHA256-based hashlocks, even 0x0000..00 needs to be accepted.
    assert secret_registry_contract.functions.registerSecret(fake_bytes(32)).call() is True
    assert secret_registry_contract.functions.registerSecret(fake_bytes(10, "02")).call() is True
    assert secret_registry_contract.functions.registerSecret(fake_bytes(32, "02")).call() is True


def test_register_secret_return_value(secret_registry_contract, get_accounts):
    """ The same secret cannot be registered twice """
    (A, B) = get_accounts(2)
    secret = b"secretsecretsecretsecretsecretse"

    # We use call here to make sure we would get the correct return value
    # even though this does not change the state
    assert secret_registry_contract.functions.registerSecret(secret).call({"from": A}) is True

    secret_registry_contract.functions.registerSecret(secret).call_and_transact({"from": A})

    # We use call here to get the return value
    assert secret_registry_contract.functions.registerSecret(secret).call({"from": A}) is False
    assert secret_registry_contract.functions.registerSecret(secret).call({"from": B}) is False


def test_register_secret(secret_registry_contract, get_accounts, get_block):
    """ Register a secret and see it's registered """
    A = get_accounts(1)[0]
    secret = b"secretsecretsecretsecretsecretse"
    secret2 = b"secretsecretsecretsecretsecretss"
    secrethash = sha256(secret).digest()

    assert secret_registry_contract.functions.getSecretRevealBlockHeight(secrethash).call() == 0

    txn_hash = secret_registry_contract.functions.registerSecret(secret).call_and_transact(
        {"from": A}
    )

    assert secret_registry_contract.functions.getSecretRevealBlockHeight(
        secrethash
    ).call() == get_block(txn_hash)

    # A should be able to register any number of secrets
    secret_registry_contract.functions.registerSecret(secret2).call_and_transact({"from": A})


def test_register_secret_batch(secret_registry_contract, get_accounts, get_block):
    """ Register four secrets and see them registered """
    (A,) = get_accounts(1)
    secrets = [fake_bytes(32, fill) for fill in ("02", "03", "04", "05")]
    secret_hashes = [sha256(secret).digest() for secret in secrets]

    for h in secret_hashes:
        assert secret_registry_contract.functions.getSecretRevealBlockHeight(h).call() == 0

    txn_hash = secret_registry_contract.functions.registerSecretBatch(secrets).call_and_transact(
        {"from": A}
    )
    block = get_block(txn_hash)

    for h in secret_hashes:
        assert secret_registry_contract.functions.getSecretRevealBlockHeight(h).call() == block


def test_register_secret_batch_return_value(secret_registry_contract, get_accounts):
    """ See registerSecret returns True only when all secrets are registered """
    (A,) = get_accounts(1)
    secrets = [fake_bytes(32, "02"), fake_bytes(32, "03"), fake_bytes(32)]

    assert secret_registry_contract.functions.registerSecretBatch(secrets).call()

    secrets[2] = fake_bytes(32, "04")
    assert secret_registry_contract.functions.registerSecretBatch(secrets).call() is True

    secret_registry_contract.functions.registerSecret(secrets[1]).call_and_transact({"from": A})
    assert secret_registry_contract.functions.registerSecretBatch(secrets).call() is False


def test_events(secret_registry_contract, event_handler):
    """ A successful registerSecret() call causes an EVENT_SECRET_REVEALED event """
    secret = b"secretsecretsecretsecretsecretse"
    secrethash = sha256(secret).digest()
    ev_handler = event_handler(secret_registry_contract)

    txn_hash = secret_registry_contract.functions.registerSecret(secret).call_and_transact()

    ev_handler.add(txn_hash, EVENT_SECRET_REVEALED, check_secret_revealed(secrethash, secret))
    ev_handler.check()


def test_register_secret_batch_events(secret_registry_contract, event_handler):
    """ A registerSecretBatch() with three secrets causes three EVENT_SECRET_REVEALED events """
    secrets = [fake_bytes(32, "02"), fake_bytes(32, "03"), fake_bytes(32, "04")]
    secret_hashes = [sha256(secret).digest() for secret in secrets]

    ev_handler = event_handler(secret_registry_contract)

    txn_hash = secret_registry_contract.functions.registerSecretBatch(secrets).call_and_transact()

    ev_handler.add(
        txn_hash, EVENT_SECRET_REVEALED, check_secrets_revealed(secret_hashes, secrets), 3
    )
    ev_handler.check()
