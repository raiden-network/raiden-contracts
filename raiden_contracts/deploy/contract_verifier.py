import json
from typing import Any, List, Optional, Tuple

from eth_typing.evm import HexAddress
from eth_utils import to_checksum_address
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    DeploymentModule,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    DeployedContracts,
    contracts_deployed_path,
    contracts_precompiled_path,
    get_contracts_deployment_info,
)
from raiden_contracts.utils.type_aliases import ChainID


class ContractVerifier:
    def __init__(self, web3: Web3, contracts_version: Optional[str] = None):
        self.web3 = web3
        self.contracts_version = contracts_version
        self.precompiled_path = contracts_precompiled_path(self.contracts_version)
        self.contract_manager = ContractManager(self.precompiled_path)

    def verify_deployed_contracts_in_filesystem(self) -> None:
        chain_id = ChainID(self.web3.eth.chain_id)

        deployment_data = get_contracts_deployment_info(
            chain_id=chain_id,
            version=self.contract_manager.contracts_version,
            module=DeploymentModule.RAIDEN,
        )
        deployment_file_path = contracts_deployed_path(
            chain_id=chain_id, version=self.contract_manager.contracts_version
        )
        if deployment_data is None:
            raise RuntimeError(f"Deployment data cannot be found at {deployment_file_path}")

        if self.verify_deployment_data(deployment_data):
            print(
                f"Deployment info from {deployment_file_path} has been verified "
                "and it is CORRECT."
            )

    def verify_deployed_service_contracts_in_filesystem(
        self,
        token_address: HexAddress,
        user_deposit_whole_balance_limit: int,
        token_network_registry_address: HexAddress,
    ) -> None:
        chain_id = ChainID(self.web3.eth.chain_id)

        deployment_data = get_contracts_deployment_info(
            chain_id=chain_id,
            version=self.contract_manager.contracts_version,
            module=DeploymentModule.SERVICES,
        )
        deployment_file_path = contracts_deployed_path(
            chain_id=chain_id, version=self.contract_manager.contracts_version, services=True
        )
        if deployment_data is None:
            raise RuntimeError(f"Deployment data cannot be found at {deployment_file_path}")

        if self.verify_service_contracts_deployment_data(
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_balance_limit,
            deployed_contracts_info=deployment_data,
            token_network_registry_address=token_network_registry_address,
        ):
            print(
                f"Deployment info from {deployment_file_path} has been verified "
                "and it is CORRECT."
            )

    def store_and_verify_deployment_info_raiden(
        self, deployed_contracts_info: DeployedContracts
    ) -> None:
        self._store_deployment_info(deployment_info=deployed_contracts_info, services=False)
        self.verify_deployed_contracts_in_filesystem()

    def store_and_verify_deployment_info_services(
        self,
        deployed_contracts_info: DeployedContracts,
        token_address: HexAddress,
        user_deposit_whole_balance_limit: int,
        token_network_registry_address: HexAddress,
    ) -> None:
        self._store_deployment_info(services=True, deployment_info=deployed_contracts_info)
        self.verify_deployed_service_contracts_in_filesystem(
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_balance_limit,
            token_network_registry_address=token_network_registry_address,
        )

    def _store_deployment_info(self, services: bool, deployment_info: DeployedContracts) -> None:
        deployment_file_path = contracts_deployed_path(
            chain_id=ChainID(self.web3.eth.chain_id),
            version=self.contracts_version,
            services=services,
        )
        with deployment_file_path.open(mode="w") as target_file:
            target_file.write(json.dumps(deployment_info, indent=2))

        print(
            f'Deployment information for chain id = {deployment_info["chain_id"]} '
            f" has been updated at {deployment_file_path}."
        )

    def verify_deployment_data(self, deployment_data: DeployedContracts) -> bool:

        if self.contract_manager.contracts_version != deployment_data["contracts_version"]:
            raise RuntimeError("Version string mismatch.")

        secret_registry, _ = self._verify_deployed_contract(
            deployment_data=deployment_data, contract_name=CONTRACT_SECRET_REGISTRY
        )

        token_network_registry, constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployment_data, contract_name=CONTRACT_TOKEN_NETWORK_REGISTRY
        )

        # We need to also check the constructor parameters against the chain
        if (
            to_checksum_address(token_network_registry.functions.secret_registry_address().call())
            != secret_registry.address
        ):
            raise RuntimeError("secret_registry_address onchain has an unexpected value.")
        if len(constructor_arguments) != 4:
            raise RuntimeError(
                "TokenNetworkRegistry received a wrong number of constructor arguments."
            )
        if secret_registry.address != constructor_arguments[0]:
            raise RuntimeError(
                "TokenNetworkRegistry's constructor received a different SecretRegistry address."
            )
        assert (
            token_network_registry.functions.settlement_timeout_min().call()
            == constructor_arguments[1]
        )
        assert (
            token_network_registry.functions.settlement_timeout_max().call()
            == constructor_arguments[2]
        )

        return True

    def _verify_deployed_contract(
        self, deployment_data: DeployedContracts, contract_name: str
    ) -> Tuple[Contract, List[Any]]:
        """Verify deployment info against the chain

        Verifies:
        - the runtime bytecode - precompiled data against the chain
        - information stored in deployment_*.json against the chain,
        except for the constructor arguments, which have to be checked
        separately.

        Returns: (onchain_instance, constructor_arguments)
        """
        contract_instance = self.contract_instance_from_deployment_data(
            deployment_data, contract_name
        )
        contracts = deployment_data["contracts"]

        # Check blockchain transaction hash & block information
        receipt = self.web3.eth.get_transaction_receipt(
            contracts[contract_name]["transaction_hash"]
        )
        if receipt["blockNumber"] != contracts[contract_name]["block_number"]:
            raise RuntimeError(
                f'We have block_number {contracts[contract_name]["block_number"]} in the '
                f'deployment info, but {receipt["blockNumber"]} in the transaction receipt '
                "from web3."
            )
        if receipt["gasUsed"] != contracts[contract_name]["gas_cost"]:
            raise RuntimeError(
                f'We have gasUsed {contracts[contract_name]["gas_cost"]} in the deployment info, '
                f'but {receipt["gasUsed"]} in the transaction receipt from web3.'
            )
        if receipt["contractAddress"] != contracts[contract_name]["address"]:
            raise RuntimeError(
                f'We have contractAddress {contracts[contract_name]["address"]} in the deployment'
                f' info but {receipt["contractAddress"]} in the transaction receipt from web3.'
            )

        # Check that the deployed bytecode matches the precompiled data
        blockchain_bytecode = self.web3.eth.get_code(contract_instance.address).hex()
        compiled_bytecode = self.contract_manager.get_runtime_hexcode(contract_name)

        if blockchain_bytecode == compiled_bytecode:
            print(
                f"{contract_name} at {contract_instance.address} "
                f"matches the compiled data from contracts.json"
            )
        else:
            raise RuntimeError(f"{contract_name} at {contract_instance.address} has wrong code")

        return contract_instance, contracts[contract_name]["constructor_arguments"]

    def contract_instance_from_deployment_data(
        self, deployment_data: DeployedContracts, contract_name: str
    ) -> Contract:
        contracts = deployment_data["contracts"]
        contract_address = contracts[contract_name]["address"]
        contract_instance = self.web3.eth.contract(
            abi=self.contract_manager.get_contract_abi(contract_name), address=contract_address
        )
        return contract_instance

    def verify_service_contracts_deployment_data(
        self,
        token_address: HexAddress,
        user_deposit_whole_balance_limit: int,
        token_network_registry_address: HexAddress,
        deployed_contracts_info: DeployedContracts,
    ) -> bool:
        chain_id = self.web3.eth.chain_id
        assert deployed_contracts_info is not None

        if self.contract_manager.contracts_version != deployed_contracts_info["contracts_version"]:
            raise RuntimeError("Version string mismatch")
        if chain_id != deployed_contracts_info["chain_id"]:
            raise RuntimeError("chain_id mismatch")

        (
            service_registry,
            service_registry_constructor_arguments,
        ) = self._verify_deployed_contract(
            deployment_data=deployed_contracts_info, contract_name=CONTRACT_SERVICE_REGISTRY
        )
        (user_deposit, user_deposit_constructor_arguments,) = self._verify_deployed_contract(
            deployment_data=deployed_contracts_info, contract_name=CONTRACT_USER_DEPOSIT
        )
        one_to_n, one_to_n_constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployed_contracts_info, contract_name=CONTRACT_ONE_TO_N
        )
        monitoring_service, ms_constructor_arguments = self._verify_deployed_contract(
            deployed_contracts_info, CONTRACT_MONITORING_SERVICE
        )
        _verify_service_registry_deployment(
            service_registry=service_registry,
            constructor_arguments=service_registry_constructor_arguments,
            token_address=token_address,
        )
        _verify_user_deposit_deployment(
            user_deposit=user_deposit,
            constructor_arguments=user_deposit_constructor_arguments,
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_balance_limit,
            one_to_n_address=one_to_n.address,
            monitoring_service_address=monitoring_service.address,
        )
        _verify_monitoring_service_deployment(
            monitoring_service=monitoring_service,
            constructor_arguments=ms_constructor_arguments,
            token_address=token_address,
            service_registry_address=service_registry.address,
            user_deposit_address=user_deposit.address,
            token_network_registry_address=token_network_registry_address,
        )
        _verify_one_to_n_deployment(
            one_to_n=one_to_n,
            constructor_arguments=one_to_n_constructor_arguments,
            user_deposit_address=user_deposit.address,
            chain_id=chain_id,
            service_registry_address=service_registry.address,
        )
        return True


def _verify_user_deposit_deployment(
    user_deposit: Contract,
    constructor_arguments: List,
    token_address: HexAddress,
    user_deposit_whole_balance_limit: int,
    one_to_n_address: HexAddress,
    monitoring_service_address: HexAddress,
) -> None:
    """Check an onchain deployment of UserDeposit and constructor arguments at deployment time"""
    if len(constructor_arguments) != 2:
        raise RuntimeError("UserDeposit has a wrong number of constructor arguments.")
    if token_address != constructor_arguments[0]:
        raise RuntimeError("UserDeposit received a wrong token address during construction.")
    if to_checksum_address(user_deposit.functions.token().call()) != token_address:
        raise RuntimeError("UserDeposit has a wrong token address onchain.")
    if user_deposit.functions.whole_balance_limit().call() != user_deposit_whole_balance_limit:
        raise RuntimeError("UserDeposit has a wrong whole_balance_limit onchain")
    if user_deposit_whole_balance_limit != constructor_arguments[1]:
        raise RuntimeError("UserDeposit received a wrong whole_balance_limit during construction.")
    if to_checksum_address(user_deposit.functions.one_to_n_address().call()) != one_to_n_address:
        raise RuntimeError("UserDeposit has a wrong OneToN address onchain.")
    onchain_msc_address = to_checksum_address(user_deposit.functions.msc_address().call())
    if onchain_msc_address != monitoring_service_address:
        raise RuntimeError(
            f"MSC address found onchain: {onchain_msc_address}, "
            f"expected: {monitoring_service_address}"
        )


def _verify_monitoring_service_deployment(
    monitoring_service: Contract,
    constructor_arguments: List,
    token_address: HexAddress,
    service_registry_address: HexAddress,
    user_deposit_address: HexAddress,
    token_network_registry_address: HexAddress,
) -> None:
    """Check an onchain deployment of MonitoringService and constructor arguments"""
    if len(constructor_arguments) != 4:
        raise RuntimeError("MonitoringService has a wrong number of constructor arguments.")
    if to_checksum_address(monitoring_service.functions.token().call()) != token_address:
        raise RuntimeError("MonitoringService has a wrong token address onchain.")
    if token_address != constructor_arguments[0]:
        raise RuntimeError("MonitoringService received a wrong token address during construction")

    if (
        to_checksum_address(monitoring_service.functions.service_registry().call())
        != service_registry_address
    ):
        raise RuntimeError("MonitoringService has a wrong ServiceRegistry address onchain.")
    if service_registry_address != constructor_arguments[1]:
        raise RuntimeError("MonitoringService received a wrong address during construction.")
    if (
        to_checksum_address(monitoring_service.functions.user_deposit().call())
        != user_deposit_address
    ):
        raise RuntimeError("MonitoringService has a wrong UserDeposit address onchain.")
    if user_deposit_address != constructor_arguments[2]:
        raise RuntimeError(
            "MonitoringService received a wrong UserDeposit address during construction."
        )
    if (
        to_checksum_address(monitoring_service.functions.token_network_registry().call())
        != token_network_registry_address
    ):
        raise RuntimeError("MonitoringService has a wrong TokenNetworkRegistry address onchain.")
    if token_network_registry_address != constructor_arguments[3]:
        raise RuntimeError(
            "MonitoringService received a wrong TokenNetworkRegistry address during construction."
        )


def _verify_one_to_n_deployment(
    one_to_n: Contract,
    constructor_arguments: List,
    user_deposit_address: HexAddress,
    service_registry_address: HexAddress,
    chain_id: int,
) -> None:
    """Check an onchain deployment of OneToN and constructor arguments"""
    if to_checksum_address(one_to_n.functions.deposit_contract().call()) != user_deposit_address:
        raise RuntimeError("OneToN has a wrong UserDeposit address onchain.")
    if user_deposit_address != constructor_arguments[0]:
        raise RuntimeError("OneToN received a wrong UserDeposit address during construction.")
    if chain_id != constructor_arguments[1]:
        raise RuntimeError("OneToN received a wrong chain ID during construction.")
    if service_registry_address != constructor_arguments[2]:
        raise RuntimeError("OneToN received a wrong ServiceRegistry address during construction.")
    if len(constructor_arguments) != 3:
        raise RuntimeError("OneToN received a wrong number of constructor arguments.")


def _verify_service_registry_deployment(
    service_registry: Contract, constructor_arguments: List, token_address: HexAddress
) -> None:
    """Check an onchain deployment of ServiceRegistry and constructor arguments"""
    if len(constructor_arguments) != 8:
        raise RuntimeError(
            "ServiceRegistry was deployed with a wrong number of constructor arguments"
        )
    if to_checksum_address(service_registry.functions.token().call()) != token_address:
        raise RuntimeError("ServiceRegistry has a wrong token address")
    if token_address != constructor_arguments[0]:
        raise RuntimeError(
            f"expected token address {token_address} "
            f"but the constructor argument for {CONTRACT_SERVICE_REGISTRY} is "
            f"{constructor_arguments[0]}"
        )
    controller_onchain = to_checksum_address(service_registry.functions.controller().call())
    if controller_onchain != constructor_arguments[1]:
        raise RuntimeError(
            f"the deployment data contains the controller address {constructor_arguments[1]} "
            f"but the contract remembers {controller_onchain} onchain."
        )
    # All other parameters can change after the deployment, so the checks are omitted.
