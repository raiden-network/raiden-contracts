from enum import Enum, IntEnum

from eth_utils import to_canonical_address

# Do not change this, this is handled by bumpversion with .bumpversion_contracts.cfg
CONTRACTS_VERSION = "0.3._"

# Contract names
CONTRACT_ENDPOINT_REGISTRY = 'EndpointRegistry'
CONTRACT_HUMAN_STANDARD_TOKEN = 'HumanStandardToken'
CONTRACT_TOKEN_NETWORK_REGISTRY = 'TokenNetworkRegistry'
CONTRACT_TOKEN_NETWORK = 'TokenNetwork'
CONTRACT_SECRET_REGISTRY = 'SecretRegistry'
CONTRACT_CUSTOM_TOKEN = 'CustomToken'
CONTRACT_CUSTOM_TOKEN_NO_DECIMALS = 'CustomTokenNoDecimals'
CONTRACT_MONITORING_SERVICE = 'MonitoringService'
CONTRACT_RAIDEN_SERVICE_BUNDLE = 'RaidenServiceBundle'

# Deployed contract information
# Deployed to Ropsten revival on 2018-09-03 from
# raiden-contracts@fc1c79329a165c738fc55c3505cf801cc79872e4
ROPSTEN_TOKEN_NETWORK_REGISTRY_ADDRESS = '0xf2a175A52Bd3c815eD7500c765bA19652AB89B30'
ROPSTEN_ENDPOINT_REGISTRY_ADDRESS = '0xEEADDC1667B6EBc7784721B123a6F669B69Eb9bD'
ROPSTEN_SECRET_REGISTRY_ADDRESS = '0x16a25511A92C5ebfc6C30ad98F754e4c820c6822'
# Deployed to Ropsten revival on 2018-09-21 from
# raiden-contracts@bfb24fed3ebda2799e4d11ad1bb5a6de116bd12d
ROPSTEN_LIMITS_TOKEN_NETWORK_REGISTRY_ADDRESS = '0x6cC27CBF184B4177CD3c5D1a39a875aD07345eEb'
ROPSTEN_LIMITS_ENDPOINT_REGISTRY_ADDRESS = '0xcF47EDF0D951c862ED9825F47075c15BEAf5Db1B'
ROPSTEN_LIMITS_SECRET_REGISTRY_ADDRESS = '0x8167a262Fa3Be92F05420675c3b409c64Be3d348'

# Timeouts
TEST_SETTLE_TIMEOUT_MIN = 5
TEST_SETTLE_TIMEOUT_MAX = 100000

DEPLOY_SETTLE_TIMEOUT_MIN = 500  # ~ 2 hours
DEPLOY_SETTLE_TIMEOUT_MAX = 555428  # ~ 3 months

# Temporary deposit limits for the Red Eyes release in WEI
MAX_ETH_CHANNEL_PARTICIPANT = int(0.075 * 10**18)
MAX_ETH_TOKEN_NETWORK = int(250 * 10**18)

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


# Index for return information from TokenNetwork.getChannelInfo
class ChannelInfoIndex(IntEnum):
    SETTLE_BLOCK = 0
    STATE = 1


# Index for return information from TokenNetwork.getChannelParticipantInfo
class ParticipantInfoIndex(IntEnum):
    DEPOSIT = 0
    WITHDRAWN = 1
    IS_CLOSER = 2
    BALANCE_HASH = 3
    NONCE = 4
    LOCKSROOT = 5
    LOCKED_AMOUNT = 6


# Meaning of values returned by TokenNetwork.getChannelInfo[ChannelInfoIndex.STATE]
class ChannelState(IntEnum):
    NONEXISTENT = 0
    OPENED = 1
    CLOSED = 2
    SETTLED = 3
    REMOVED = 4


# Message types, as used by the TokenNetwork contract
class MessageTypeId(IntEnum):
    BALANCE_PROOF = 1
    BALANCE_PROOF_UPDATE = 2
    WITHDRAW = 3
    COOPERATIVE_SETTLE = 4


# Network configurations
START_QUERY_BLOCK_KEY = 'DefaultStartBlock'


class ChainId(IntEnum):
    MAINNET = 1
    ROPSTEN = 3
    RINKEBY = 4
    KOVAN = 42
    SMOKETEST = 627


MAINNET = 'mainnet'
ROPSTEN = 'ropsten'
RINKEBY = 'rinkeby'
KOVAN = 'kovan'
SMOKETEST = 'smoketest'

ID_TO_NETWORKNAME = {
    ChainId.MAINNET: MAINNET,
    ChainId.ROPSTEN: ROPSTEN,
    ChainId.RINKEBY: RINKEBY,
    ChainId.KOVAN: KOVAN,
    ChainId.SMOKETEST: SMOKETEST,
}


NETWORKNAME_TO_ID = {
    name: id
    for id, name in ID_TO_NETWORKNAME.items()
}


class NetworkType(Enum):
    MAIN = 1
    TEST = 2


ID_TO_NETWORK_CONFIG = {
    ChainId.ROPSTEN: {
        NetworkType.TEST: {
            'network_type': NetworkType.TEST,
            'contract_addresses': {
                CONTRACT_ENDPOINT_REGISTRY: to_canonical_address(
                    ROPSTEN_ENDPOINT_REGISTRY_ADDRESS,
                ),
                CONTRACT_SECRET_REGISTRY: to_canonical_address(ROPSTEN_SECRET_REGISTRY_ADDRESS),
                CONTRACT_TOKEN_NETWORK_REGISTRY: to_canonical_address(
                    ROPSTEN_TOKEN_NETWORK_REGISTRY_ADDRESS,
                ),
            },
            # 924 blocks before token network registry deployment
            START_QUERY_BLOCK_KEY: 3604000,
        },
        NetworkType.MAIN: {
            'network_type': NetworkType.MAIN,
            'contract_addresses': {
                CONTRACT_ENDPOINT_REGISTRY: to_canonical_address(
                    ROPSTEN_LIMITS_ENDPOINT_REGISTRY_ADDRESS,
                ),
                CONTRACT_SECRET_REGISTRY: to_canonical_address(
                    ROPSTEN_LIMITS_SECRET_REGISTRY_ADDRESS,
                ),
                CONTRACT_TOKEN_NETWORK_REGISTRY: to_canonical_address(
                    ROPSTEN_LIMITS_TOKEN_NETWORK_REGISTRY_ADDRESS,
                ),
            },
            # 153 blocks before token network registry deployment
            START_QUERY_BLOCK_KEY: 4084000,
        },
    },
}
