from collections import namedtuple
from enum import Enum, IntEnum
from typing import Dict

from eth_typing import ChecksumAddress, HexAddress, HexStr
from eth_utils import keccak

from raiden_contracts.utils.type_aliases import ChainID, Locksroot

# The last digit is supposed to be zero always. See `RELEASE.rst`.
CONTRACTS_VERSION = "0.40.0"
CORUSCANT_VERSION = "0.40.0"
BESPIN_VERSION = "0.37.0"
ALDERAAN_VERSION = "0.37.0"

PRECOMPILED_DATA_FIELDS = ["abi", "bin", "bin-runtime", "metadata"]

# Contract names
CONTRACT_HUMAN_STANDARD_TOKEN = "HumanStandardToken"
CONTRACT_TOKEN_NETWORK_REGISTRY = "TokenNetworkRegistry"
CONTRACT_TOKEN_NETWORK = "TokenNetwork"
CONTRACT_SECRET_REGISTRY = "SecretRegistry"
CONTRACT_CUSTOM_TOKEN = "CustomToken"
CONTRACT_CUSTOM_TOKEN_NO_DECIMALS = "CustomTokenNoDecimals"
CONTRACT_MONITORING_SERVICE = "MonitoringService"
CONTRACT_SERVICE_REGISTRY = "ServiceRegistry"
CONTRACT_USER_DEPOSIT = "UserDeposit"
CONTRACT_ONE_TO_N = "OneToN"
CONTRACT_DEPOSIT = "Deposit"

# Timeouts
TEST_SETTLE_TIMEOUT_MIN = 5
TEST_SETTLE_TIMEOUT_MAX = 100000

DEPLOY_SETTLE_TIMEOUT_MIN = 500  # ~ 2 hours
DEPLOY_SETTLE_TIMEOUT_MAX = 555428  # ~ 3 months

# Temporary deposit limits for the Red Eyes release in WEI
MAX_ETH_CHANNEL_PARTICIPANT = int(0.075 * 10 ** 18)
MAX_ETH_TOKEN_NETWORK = int(250 * 10 ** 18)

# Special hashes
LOCKSROOT_OF_NO_LOCKS = Locksroot(keccak(b""))
EMPTY_ADDRESS = ChecksumAddress(HexAddress(HexStr("0x0000000000000000000000000000000000000000")))

# Event names
# TokenNetworkRegistry
EVENT_TOKEN_NETWORK_CREATED = "TokenNetworkCreated"

# TokenNetwork
EVENT_DEPRECATION_SWITCH = "DeprecationSwitch"

# SecretRegistry
EVENT_SECRET_REVEALED = "SecretRevealed"

# EndpointRegistry
EVENT_ADDRESS_REGISTERED = "AddressRegistered"

# ServiceRegistry
EVENT_REGISTERED_SERVICE = "RegisteredService"


class ChannelEvent(str, Enum):
    OPENED = "ChannelOpened"
    DEPOSIT = "ChannelNewDeposit"
    WITHDRAW = "ChannelWithdraw"
    BALANCE_PROOF_UPDATED = "NonClosingBalanceProofUpdated"
    CLOSED = "ChannelClosed"
    SETTLED = "ChannelSettled"
    UNLOCKED = "ChannelUnlocked"
    DEPRECATED = "DeprecationSwitch"


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
    IOU = 5
    MSReward = 6


class MonitoringServiceEvent(str, Enum):
    """Message types used by MonitoringService contract"""

    NEW_BALANCE_PROOF_RECEIVED = "NewBalanceProofReceived"
    REWARD_CLAIMED = "RewardClaimed"


class UserDepositEvent(str, Enum):
    """Message types used by UserDeposit contract"""

    BALANCE_REDUCED = "BalanceReduced"
    WITHDRAW_PLANNED = "WithdrawPlanned"


class OneToNEvent(str, Enum):
    """Message types used by OneToN contract"""

    CLAIMED = "Claimed"


class DeploymentModule(Enum):
    """Groups of contracts that are deployed together"""

    RAIDEN = "raiden"
    SERVICES = "services"
    ALL = "all"


# Network configurations
START_QUERY_BLOCK_KEY = "DefaultStartBlock"

ID_TO_CHAINNAME: Dict[ChainID, str] = {
    ChainID(-5): "goerli_unstable",
    ChainID(1): "mainnet",
    ChainID(3): "ropsten",
    ChainID(4): "rinkeby",
    ChainID(5): "goerli",
    ChainID(42): "kovan",
    ChainID(627): "smoketest",
}

CHAINNAME_TO_ID: Dict[str, ChainID] = {name: id for id, name in ID_TO_CHAINNAME.items()}

# ContractNames


ContractListEntry = namedtuple("ContractListEntry", "module name")

CONTRACT_LIST = [
    ContractListEntry(module=DeploymentModule.RAIDEN, name=CONTRACT_SECRET_REGISTRY),
    ContractListEntry(module=DeploymentModule.RAIDEN, name=CONTRACT_TOKEN_NETWORK_REGISTRY),
    ContractListEntry(module=DeploymentModule.RAIDEN, name=CONTRACT_TOKEN_NETWORK),
    ContractListEntry(module=DeploymentModule.SERVICES, name=CONTRACT_SERVICE_REGISTRY),
    ContractListEntry(module=DeploymentModule.SERVICES, name=CONTRACT_MONITORING_SERVICE),
    ContractListEntry(module=DeploymentModule.SERVICES, name=CONTRACT_ONE_TO_N),
    ContractListEntry(module=DeploymentModule.SERVICES, name=CONTRACT_USER_DEPOSIT),
]
