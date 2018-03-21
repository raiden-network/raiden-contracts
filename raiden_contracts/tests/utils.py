def check_secret_revealed(secret):
    def get(event):
        assert event['args']['secret'] == secret
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
