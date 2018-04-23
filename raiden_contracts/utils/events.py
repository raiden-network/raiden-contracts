def check_secret_revealed(secrethash):
    def get(event):
        assert event['args']['secrethash'] == secrethash
    return get


def check_token_network_created(token_address, token_network_address):
    def get(event):
        assert event['args']['token_address'] == token_address
        assert event['args']['token_network_address'] == token_network_address
    return get


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


def check_channel_closed(channel_identifier, closing_participant):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['closing_participant'] == closing_participant
    return get


def check_channel_unlocked(channel_identifier, participant, unlocked_amount, returned_tokens):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant'] == participant
        assert event['args']['unlocked_amount'] == unlocked_amount
        assert event['args']['returned_tokens'] == returned_tokens
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
