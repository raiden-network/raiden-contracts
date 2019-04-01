from enum import Enum, IntEnum

# Do not change this, this is handled by bumpversion with .bumpversion_contracts.cfg
CONTRACTS_VERSION = '0.11.0'

PRECOMPILED_DATA_FIELDS = ['abi', 'bin', 'bin-runtime', 'metadata']

# Contract names
CONTRACT_ENDPOINT_REGISTRY = 'EndpointRegistry'
CONTRACT_HUMAN_STANDARD_TOKEN = 'HumanStandardToken'
CONTRACT_TOKEN_NETWORK_REGISTRY = 'TokenNetworkRegistry'
CONTRACT_TOKEN_NETWORK = 'TokenNetwork'
CONTRACT_SECRET_REGISTRY = 'SecretRegistry'
CONTRACT_CUSTOM_TOKEN = 'CustomToken'
CONTRACT_CUSTOM_TOKEN_NO_DECIMALS = 'CustomTokenNoDecimals'
CONTRACT_MONITORING_SERVICE = 'MonitoringService'
CONTRACT_RAIDEN_SERVICE_BUNDLE = 'ServiceRegistry'  # old name for compatibility, deprecated
CONTRACT_SERVICE_REGISTRY = 'ServiceRegistry'
CONTRACT_USER_DEPOSIT = 'UserDeposit'
CONTRACT_ONE_TO_N = 'OneToN'

# Timeouts
TEST_SETTLE_TIMEOUT_MIN = 5
TEST_SETTLE_TIMEOUT_MAX = 100000

DEPLOY_SETTLE_TIMEOUT_MIN = 500  # ~ 2 hours
DEPLOY_SETTLE_TIMEOUT_MAX = 555428  # ~ 3 months

# Temporary deposit limits for the Red Eyes release in WEI
MAX_ETH_CHANNEL_PARTICIPANT = int(0.075 * 10**18)
MAX_ETH_TOKEN_NETWORK = int(250 * 10**18)

GAS_REQUIRED_FOR_CREATE_TOKEN_NETWORK = 3234716
GAS_REQUIRED_FOR_OPEN_CHANNEL = 112922
GAS_REQUIRED_FOR_SET_TOTAL_DEPOSIT = 60110
GAS_REQUIRED_FOR_CLOSE_CHANNEL = 112715
GAS_REQUIRED_FOR_UPDATE_BALANCE_PROOF = 96348
GAS_REQUIRED_FOR_SETTLE_CHANNEL = 125052
GAS_REQUIRED_FOR_UNLOCK_1_LOCKS = 33515
GAS_REQUIRED_FOR_UNLOCK_6_LOCKS = 72944

GAS_REQUIRED_FOR_REGISTER_SECRET = 46161
GAS_REQUIRED_FOR_ENDPOINT_REGISTER = 49183

GAS_REQUIRED_FOR_MS_MONITOR = 203802
GAS_REQUIRED_FOR_MS_CLAIM_REWARD = 42647
GAS_REQUIRED_FOR_ONE_TO_N_CLAIM = 90766
GAS_REQUIRED_FOR_UDC_DEPOSIT = 101311
GAS_REQUIRED_FOR_UDC_INCREASE_DEPOSIT = 28156
GAS_REQUIRED_FOR_UDC_PLAN_WITHDRAW = 64021
GAS_REQUIRED_FOR_UDC_WITHDRAW = 40079

# Event names
# TokenNetworkRegistry
EVENT_TOKEN_NETWORK_CREATED = 'TokenNetworkCreated'

# SecretRegistry
EVENT_SECRET_REVEALED = 'SecretRevealed'

# EndpointRegistry
EVENT_ADDRESS_REGISTERED = 'AddressRegistered'


class ChannelEvent(str, Enum):
    OPENED = 'ChannelOpened'
    DEPOSIT = 'ChannelNewDeposit'
    WITHDRAW = 'ChannelWithdraw'
    BALANCE_PROOF_UPDATED = 'NonClosingBalanceProofUpdated'
    CLOSED = 'ChannelClosed'
    SETTLED = 'ChannelSettled'
    UNLOCKED = 'ChannelUnlocked'


class ChannelInfoIndex(IntEnum):
    """Index for accessing fields in return information from TokenNetwork.getChannelInfo."""
    SETTLE_BLOCK = 0
    STATE = 1


class ParticipantInfoIndex(IntEnum):
    """Index for accessing fields in return value of TokenNetwork.getChannelParticipantInfo."""
    DEPOSIT = 0
    WITHDRAWN = 1
    IS_CLOSER = 2
    BALANCE_HASH = 3
    NONCE = 4
    LOCKSROOT = 5
    LOCKED_AMOUNT = 6


class ChannelState(IntEnum):
    """Meaning of values returned by TokenNetwork.getChannelInfo[ChannelInfoIndex.STATE]"""
    NONEXISTENT = 0
    OPENED = 1
    CLOSED = 2
    SETTLED = 3
    REMOVED = 4


class MessageTypeId(IntEnum):
    """Message types, as used by the TokenNetwork contract"""
    BALANCE_PROOF = 1
    BALANCE_PROOF_UPDATE = 2
    WITHDRAW = 3
    COOPERATIVE_SETTLE = 4


class MonitoringServiceEvent(str, Enum):
    """Message types used by MonitoringService contract"""
    NEW_BALANCE_PROOF_RECEIVED = 'NewBalanceProofReceived'
    REWARD_CLAIMED = 'RewardClaimed'


class UserDepositEvent(str, Enum):
    """Message types used by UserDeposit contract"""
    BALANCE_REDUCED = 'BalanceReduced'
    WITHDRAW_PLANNED = 'WithdrawPlanned'


class OneToNEvent(str, Enum):
    """Message types used by OneToN contract"""
    CLAIMED = 'Claimed'


class DeploymentModule(Enum):
    """Groups of contracts that are deployed together"""
    RAIDEN = 'raiden'
    SERVICES = 'services'
    ALL = 'all'


# Network configurations
START_QUERY_BLOCK_KEY = 'DefaultStartBlock'

ID_TO_NETWORKNAME = {
    1: 'mainnet',
    3: 'ropsten',
    4: 'rinkeby',
    42: 'kovan',
    627: 'smoketest',
}

NETWORKNAME_TO_ID = {
    name: id
    for id, name in ID_TO_NETWORKNAME.items()
}
