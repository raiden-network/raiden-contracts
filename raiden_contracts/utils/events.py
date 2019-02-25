def check_secret_revealed(secrethash, secret):
    def get(event):
        assert event['args']['secrethash'] == secrethash
        assert event['args']['secret'] == secret
    return get


def check_secrets_revealed(secrethashes, secrets):
    def get(event):
        assert event['args']['secrethash'] in secrethashes
        assert event['args']['secret'] in secrets
    return get


def check_token_network_created(token_address, token_network_address):
    def get(event):
        assert event['args']['token_address'] == token_address
        assert event['args']['token_network_address'] == token_network_address
    return get


def check_address_registered(eth_address, endpoint):
    def get(event):
        assert event['args']['eth_address'] == eth_address
        assert event['args']['endpoint'] == endpoint
    return get


def check_channel_opened(channel_identifier, participant1, participant2, settle_timeout):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant1'] == participant1
        assert event['args']['participant2'] == participant2
        assert event['args']['settle_timeout'] == settle_timeout
    return get


# Check TokenNetwork.ChannelNewDeposit events. Not for UDC deposits!
def check_new_deposit(channel_identifier, participant, deposit):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant'] == participant
        assert event['args']['total_deposit'] == deposit
    return get


def check_withdraw(channel_identifier, participant, withdrawn_amount):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant'] == participant
        assert event['args']['total_withdraw'] == withdrawn_amount
    return get


def check_channel_closed(channel_identifier, closing_participant, nonce):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['closing_participant'] == closing_participant
        assert event['args']['nonce'] == nonce
    return get


def check_channel_unlocked(
        channel_identifier,
        participant,
        partner,
        locksroot,
        unlocked_amount,
        returned_tokens,
):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant'] == participant
        assert event['args']['partner'] == partner
        assert event['args']['locksroot'] == locksroot
        assert event['args']['unlocked_amount'] == unlocked_amount
        assert event['args']['returned_tokens'] == returned_tokens
    return get


def check_transfer_updated(channel_identifier, closing_participant, nonce):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['closing_participant'] == closing_participant
        assert event['args']['nonce'] == nonce
    return get


def check_channel_settled(channel_identifier, participant1_amount, participant2_amount):
    def get(event):
        assert event['args']['channel_identifier'] == channel_identifier
        assert event['args']['participant1_amount'] == participant1_amount
        assert event['args']['participant2_amount'] == participant2_amount
    return get
