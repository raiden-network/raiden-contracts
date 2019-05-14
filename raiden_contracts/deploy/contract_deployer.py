from logging import getLogger
from typing import Any, Dict, List, Optional

from eth_utils import encode_hex, is_address, to_checksum_address
from eth_utils.units import units
from web3 import Web3
from web3.contract import Contract, ContractFunction
from web3.middleware import construct_sign_and_send_raw_middleware

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    CONTRACTS_VERSION,
    DEPLOY_SETTLE_TIMEOUT_MAX,
    DEPLOY_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.contract_manager import DeployedContract, contract_version_string
from raiden_contracts.contract_source_manager import ContractSourceManager, contracts_source_path
from raiden_contracts.deploy.contract_verifier import ContractVerifier, DeployedContracts
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.transaction import check_successful_tx
from raiden_contracts.utils.versions import contracts_version_expects_deposit_limits

LOG = getLogger(__name__)


class ContractDeployer(ContractVerifier):
    def __init__(
        self,
        web3: Web3,
        private_key: str,
        gas_limit: int,
        gas_price: int = 1,
        wait: int = 10,
        contracts_version: Optional[str] = None,
    ):
        # pylint: disable=E1101
        super(ContractDeployer, self).__init__(web3=web3, contracts_version=contracts_version)
        self.wait = wait
        self.owner = private_key_to_address(private_key)
        self.transaction = {"from": self.owner, "gas": gas_limit}
        if gas_price != 0:
            self.transaction["gasPrice"] = gas_price * int(units["gwei"])

        self.web3.middleware_stack.add(construct_sign_and_send_raw_middleware(private_key))

        # Check that the precompiled data matches the source code
        # Only for current version, because this is the only one with source code
        if self.contracts_version in [None, CONTRACTS_VERSION]:
            contract_manager_source = ContractSourceManager(contracts_source_path())
            contract_manager_source.checksum_contracts()
            contract_manager_source.verify_precompiled_checksums(self.precompiled_path)
        else:
            LOG.info("Skipped checks against the source code because it is not available.")

    def deploy(self, contract_name: str, args=None):
        if args is None:
            args = list()
        contract_interface: DeployedContract = self.contract_manager.get_contract(contract_name)

        # Instantiate and deploy contract
        contract = self.web3.eth.contract(
            abi=contract_interface["abi"], bytecode=contract_interface["bin"]
        )

        # Get transaction hash from deployed contract
        txhash = self.send_deployment_transaction(contract=contract, args=args)

        # Get tx receipt to get contract address
        LOG.debug(
            f"Deploying {contract_name} txHash={encode_hex(txhash)}, "
            f"contracts version {self.contract_manager.contracts_version}"
        )
        (receipt, tx) = check_successful_tx(web3=self.web3, txid=txhash, timeout=self.wait)
        if not receipt["contractAddress"]:  # happens with Parity
            receipt = dict(receipt)
            receipt["contractAddress"] = tx["creates"]
        LOG.info(
            "{0} address: {1}. Gas used: {2}".format(
                contract_name, receipt["contractAddress"], receipt["gasUsed"]
            )
        )
        return receipt

    def transact(self, contract_method: ContractFunction):
        """ A wrapper around to_be_called.transact() that waits until the transaction succeeds. """
        txhash = contract_method.transact(self.transaction)
        LOG.debug(f"Sending txHash={encode_hex(txhash)}")
        (receipt, _) = check_successful_tx(web3=self.web3, txid=txhash, timeout=self.wait)
        return receipt

    def send_deployment_transaction(self, contract, args):
        txhash = None
        while txhash is None:
            try:
                txhash = contract.constructor(*args).transact(self.transaction)
            except ValueError as ex:
                # pylint: disable=E1126
                if ex.args[0]["code"] == -32015:
                    LOG.info(f"Deployment failed with {ex}. Retrying...")
                else:
                    raise ex

        return txhash

    def contract_version_string(self):
        return contract_version_string(self.contracts_version)

    def deploy_token_contract(
        self,
        token_supply: int,
        token_decimals: int,
        token_name: str,
        token_symbol: str,
        token_type: str = "CustomToken",
    ):
        """Deploy a token contract."""
        receipt = self.deploy(
            contract_name=token_type, args=[token_supply, token_decimals, token_name, token_symbol]
        )
        token_address = receipt["contractAddress"]
        assert token_address and is_address(token_address)
        token_address = to_checksum_address(token_address)
        return {token_type: token_address}

    def deploy_raiden_contracts(
        self, max_num_of_token_networks: Optional[int]
    ) -> DeployedContracts:
        """ Deploy all required raiden contracts and return a dict of contract_name:address

        Args:
            max_num_of_token_networks (Optional[int]): The max number of tokens that can be
            registered to the TokenNetworkRegistry. If None, the argument is omitted from
            the call to the constructor of TokenNetworkRegistry.
        """

        deployed_contracts: DeployedContracts = {
            "contracts_version": self.contract_version_string(),
            "chain_id": int(self.web3.version.network),
            "contracts": {},
        }

        self._deploy_and_remember(CONTRACT_ENDPOINT_REGISTRY, [], deployed_contracts)
        secret_registry = self._deploy_and_remember(
            contract_name=CONTRACT_SECRET_REGISTRY,
            arguments=[],
            deployed_contracts=deployed_contracts,
        )
        token_network_registry_args = [
            secret_registry.address,
            deployed_contracts["chain_id"],
            DEPLOY_SETTLE_TIMEOUT_MIN,
            DEPLOY_SETTLE_TIMEOUT_MAX,
        ]
        if max_num_of_token_networks:
            token_network_registry_args.append(max_num_of_token_networks)
        self._deploy_and_remember(
            contract_name=CONTRACT_TOKEN_NETWORK_REGISTRY,
            arguments=token_network_registry_args,
            deployed_contracts=deployed_contracts,
        )

        return deployed_contracts

    def _deploy_and_remember(
        self, contract_name: str, arguments: List, deployed_contracts: "DeployedContracts"
    ) -> Contract:
        """ Deploys contract_name with arguments and store the result in deployed_contracts. """
        receipt = self.deploy(contract_name, arguments)
        deployed_contracts["contracts"][contract_name] = _deployed_data_from_receipt(
            receipt=receipt, constructor_arguments=arguments
        )
        return self.web3.eth.contract(
            abi=self.contract_manager.get_contract_abi(contract_name),
            address=deployed_contracts["contracts"][contract_name]["address"],
        )

    def register_token_network(
        self,
        token_registry_abi: List[Dict[str, Any]],
        token_registry_address: str,
        token_address: str,
        channel_participant_deposit_limit: Optional[int],
        token_network_deposit_limit: Optional[int],
    ):
        """Register token with a TokenNetworkRegistry contract."""
        with_limits = contracts_version_expects_deposit_limits(self.contracts_version)
        if with_limits:
            return self._register_token_network_with_limits(
                token_registry_abi,
                token_registry_address,
                token_address,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            )
        else:
            return self._register_token_network_without_limits(
                token_registry_abi,
                token_registry_address,
                token_address,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            )

    def _register_token_network_without_limits(
        self,
        token_registry_abi: List[Dict[str, Any]],
        token_registry_address: str,
        token_address: str,
        channel_participant_deposit_limit: Optional[int],
        token_network_deposit_limit: Optional[int],
    ):
        """Register token with a TokenNetworkRegistry contract

        with a contracts-version that doesn't require deposit limits in the TokenNetwork
        constructor.
        """
        if channel_participant_deposit_limit:
            raise ValueError(
                "contracts_version below 0.9.0 does not expect "
                "channel_participant_deposit_limit"
            )
        if token_network_deposit_limit:
            raise ValueError(
                "contracts_version below 0.9.0 does not expect token_network_deposit_limit"
            )
        token_network_registry = self.web3.eth.contract(
            abi=token_registry_abi, address=token_registry_address
        )

        version_from_onchain = token_network_registry.functions.contract_version().call()
        if version_from_onchain != self.contract_manager.version_string:
            raise RuntimeError(
                f"got {version_from_onchain} from the chain, expected "
                f"{self.contract_manager.version_string} in the deployment data"
            )

        command = token_network_registry.functions.createERC20TokenNetwork(token_address)
        self.transact(command)

        token_network_address = token_network_registry.functions.token_to_token_networks(
            token_address
        ).call()
        token_network_address = to_checksum_address(token_network_address)
        LOG.debug(f"TokenNetwork address: {token_network_address}")
        return token_network_address

    def _register_token_network_with_limits(
        self,
        token_registry_abi: List[Dict[str, Any]],
        token_registry_address: str,
        token_address: str,
        channel_participant_deposit_limit: Optional[int],
        token_network_deposit_limit: Optional[int],
    ):
        """Register token with a TokenNetworkRegistry contract

        with a contracts-version that requires deposit limits in the TokenNetwork
        constructor.
        """
        if channel_participant_deposit_limit is None:
            raise ValueError(
                "contracts_version 0.9.0 and afterwards expect "
                "channel_participant_deposit_limit"
            )
        if token_network_deposit_limit is None:
            raise ValueError(
                "contracts_version 0.9.0 and afterwards expect " "token_network_deposit_limit"
            )
        token_network_registry = self.web3.eth.contract(
            abi=token_registry_abi, address=token_registry_address
        )

        version_from_onchain = token_network_registry.functions.contract_version().call()
        if version_from_onchain != self.contract_manager.version_string:
            raise RuntimeError(
                f"got {version_from_onchain} from the chain, expected "
                f"{self.contract_manager.version_string()} in the deployment data"
            )

        command = token_network_registry.functions.createERC20TokenNetwork(
            _token_address=token_address,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )
        self.transact(command)

        token_network_address = token_network_registry.functions.token_to_token_networks(
            token_address
        ).call()
        token_network_address = to_checksum_address(token_network_address)
        LOG.debug(f"TokenNetwork address: {token_network_address}")
        return token_network_address

    def deploy_service_contracts(self, token_address: str, user_deposit_whole_balance_limit: int):
        """Deploy 3rd party service contracts"""
        chain_id = int(self.web3.version.network)
        deployed_contracts: DeployedContracts = {
            "contracts_version": self.contract_version_string(),
            "chain_id": chain_id,
            "contracts": {},
        }

        self._deploy_and_remember(CONTRACT_SERVICE_REGISTRY, [token_address], deployed_contracts)
        user_deposit = self._deploy_and_remember(
            contract_name=CONTRACT_USER_DEPOSIT,
            arguments=[token_address, user_deposit_whole_balance_limit],
            deployed_contracts=deployed_contracts,
        )

        monitoring_service_constructor_args = [
            token_address,
            deployed_contracts["contracts"][CONTRACT_SERVICE_REGISTRY]["address"],
            deployed_contracts["contracts"][CONTRACT_USER_DEPOSIT]["address"],
        ]
        msc = self._deploy_and_remember(
            contract_name=CONTRACT_MONITORING_SERVICE,
            arguments=monitoring_service_constructor_args,
            deployed_contracts=deployed_contracts,
        )

        one_to_n = self._deploy_and_remember(
            contract_name=CONTRACT_ONE_TO_N,
            arguments=[user_deposit.address, chain_id],
            deployed_contracts=deployed_contracts,
        )

        # Tell the UserDeposit instance about other contracts.
        LOG.debug(
            "Calling UserDeposit.init() with "
            f"msc_address={msc.address} "
            f"one_to_n_address={one_to_n.address}"
        )
        self.transact(
            user_deposit.functions.init(
                _msc_address=msc.address, _one_to_n_address=one_to_n.address
            )
        )

        return deployed_contracts


def _deployed_data_from_receipt(receipt, constructor_arguments):
    return {
        "address": to_checksum_address(receipt["contractAddress"]),
        "transaction_hash": encode_hex(receipt["transactionHash"]),
        "block_number": receipt["blockNumber"],
        "gas_cost": receipt["gasUsed"],
        "constructor_arguments": constructor_arguments,
    }
