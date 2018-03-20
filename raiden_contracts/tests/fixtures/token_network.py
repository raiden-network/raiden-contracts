import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK


@pytest.fixture()
def get_token_network(chain, create_contract):
    def get(arguments, transaction=None):
        TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
        contract = create_contract(TokenNetwork, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def token_network(chain, token_network_registry, custom_token, secret_registry):
    token_network_address = token_network_registry.call().createERC20TokenNetwork(custom_token.address)
    token_network_registry.transact().createERC20TokenNetwork(custom_token.address)

    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    token_network = chain.web3.eth.contract(address=token_network_address, ContractFactoryClass=TokenNetwork)

    return token_network


@pytest.fixture()
def token_network_external(chain, get_token_network, custom_token, secret_registry):
    return get_token_network([custom_token.address, secret_registry.address, int(chain.web3.version.network)])


def check_channel_opened(channel_identifier, participant1, participant2, settle_timeout):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant1'] == participant1
        assert event['args']['participant2'] == participant2
        assert event['args']['settle_timeout'] == settle_timeout
    return get


def check_new_deposit(channel_identifier, participant, deposit):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant'] == participant
        assert event['args']['deposit'] == deposit
    return get


def check_channel_closed(channel_identifier, closing_address):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['closing_address'] == closing_address
    return get


def check_channel_unlocked(channel_identifier, payer_participant, transferred_amount):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['payer_participant'] == payer_participant
        assert event['args']['transferred_amount'] == transferred_amount
    return get


def check_transfer_updated(channel_identifier, closing_participant):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['closing_participant'] == closing_participant
    return get


def check_channel_settled(channel_identifier):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
    return get
