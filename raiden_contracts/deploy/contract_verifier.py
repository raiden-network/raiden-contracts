import json
from typing import List, Optional

from eth_utils import to_checksum_address
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
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
from raiden_contracts.utils.type_aliases import Address


class ContractVerifier:
    def __init__(self, web3: Web3, contracts_version: Optional[str] = None):
        self.web3 = web3
        self.contracts_version = contracts_version
        self.precompiled_path = contracts_precompiled_path(self.contracts_version)
        self.contract_manager = ContractManager(self.precompiled_path)

    def verify_deployed_contracts_in_filesystem(self) -> None:
        chain_id = int(self.web3.version.network)

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
                f"Deployment info from {deployment_file_path} has been verified"
                "and it is CORRECT."
            )

    def verify_deployed_service_contracts_in_filesystem(
        self, token_address: Address, user_deposit_whole_balance_limit: int
    ):
        chain_id = int(self.web3.version.network)

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
        ):
            print(
                f"Deployment info from {deployment_file_path} has been verified "
                "and it is CORRECT."
            )

    def store_and_verify_deployment_info_raiden(self, deployed_contracts_info: DeployedContracts):
        self._store_deployment_info(deployment_info=deployed_contracts_info, services=False)
        self.verify_deployed_contracts_in_filesystem()

    def store_and_verify_deployment_info_services(
        self,
        deployed_contracts_info: DeployedContracts,
        token_address: Address,
        user_deposit_whole_balance_limit: int,
    ):
        self._store_deployment_info(services=True, deployment_info=deployed_contracts_info)
        self.verify_deployed_service_contracts_in_filesystem(
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_balance_limit,
        )

    def _store_deployment_info(self, services: bool, deployment_info: DeployedContracts):
        deployment_file_path = contracts_deployed_path(
            chain_id=int(self.web3.version.network),
            version=self.contracts_version,
            services=services,
        )
        with deployment_file_path.open(mode="w") as target_file:
            target_file.write(json.dumps(deployment_info))

        print(
            f'Deployment information for chain id = {deployment_info["chain_id"]} '
            f" has been updated at {deployment_file_path}."
        )

    def verify_deployment_data(self, deployment_data: DeployedContracts):
        chain_id = int(self.web3.version.network)
        assert deployment_data is not None

        if self.contract_manager.version_string != deployment_data["contracts_version"]:
            raise RuntimeError("Version string mismatch.")
        if chain_id != deployment_data["chain_id"]:
            raise RuntimeError("chain id mismatch.")

        self._verify_deployed_contract(
            deployment_data=deployment_data, contract_name=CONTRACT_ENDPOINT_REGISTRY
        )

        secret_registry, _ = self._verify_deployed_contract(
            deployment_data=deployment_data, contract_name=CONTRACT_SECRET_REGISTRY
        )

        token_network_registry, constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployment_data, contract_name=CONTRACT_TOKEN_NETWORK_REGISTRY
        )

        # We need to also check the constructor parameters against the chain
        assert (
            to_checksum_address(token_network_registry.functions.secret_registry_address().call())
            == secret_registry.address
        )
        assert secret_registry.address == constructor_arguments[0]
        assert token_network_registry.functions.chain_id().call() == constructor_arguments[1]
        assert (
            token_network_registry.functions.settlement_timeout_min().call()
            == constructor_arguments[2]
        )
        assert (
            token_network_registry.functions.settlement_timeout_max().call()
            == constructor_arguments[3]
        )

        return True

    def _verify_deployed_contract(
        self, deployment_data: DeployedContracts, contract_name: str
    ) -> Contract:
        """ Verify deployment info against the chain

        Verifies:
        - the runtime bytecode - precompiled data against the chain
        - information stored in deployment_*.json against the chain,
        except for the constructor arguments, which have to be checked
        separately.

        Returns: (onchain_instance, constructor_arguments)
        """
        contracts = deployment_data["contracts"]

        contract_address = contracts[contract_name]["address"]
        contract_instance = self.web3.eth.contract(
            abi=self.contract_manager.get_contract_abi(contract_name), address=contract_address
        )

        # Check blockchain transaction hash & block information
        receipt = self.web3.eth.getTransactionReceipt(contracts[contract_name]["transaction_hash"])
        if receipt["blockNumber"] != contracts[contract_name]["block_number"]:
            raise RuntimeError(
                f'We have block_number {contracts[contract_name]["block_number"]} in the '
                f'deployment info, but {receipt["blockNumber"]} in the transaction receipt'
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
        blockchain_bytecode = self.web3.eth.getCode(contract_address).hex()
        compiled_bytecode = self.contract_manager.get_runtime_hexcode(contract_name)
        if blockchain_bytecode == compiled_bytecode:
            print(
                f"{contract_name} at {contract_address} "
                f"matches the compiled data from contracts.json"
            )
        else:
            raise RuntimeError(f"{contract_name} at {contract_address} has wrong code")

        # Check the contract version
        version = contract_instance.functions.contract_version().call()

        # It's an assert because the caller of this function should have checked this.
        assert version == deployment_data["contracts_version"], (
            f'got {version} expected {deployment_data["contracts_version"]}. '
            "contract_manager has contracts_version"
            f"{self.contract_manager.contracts_version}"
        )

        return contract_instance, contracts[contract_name]["constructor_arguments"]

    def verify_service_contracts_deployment_data(
        self,
        token_address: Address,
        user_deposit_whole_balance_limit: int,
        deployed_contracts_info: DeployedContracts,
    ):
        chain_id = int(self.web3.version.network)
        assert deployed_contracts_info is not None

        if self.contract_manager.version_string != deployed_contracts_info["contracts_version"]:
            raise RuntimeError("Version string mismatch")
        if chain_id != deployed_contracts_info["chain_id"]:
            raise RuntimeError("chain_id mismatch")

        service_registry, service_registry_constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployed_contracts_info, contract_name=CONTRACT_SERVICE_REGISTRY
        )
        user_deposit, user_deposit_constructor_arguments = self._verify_deployed_contract(
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
        )
        _verify_one_to_n_deployment(
            one_to_n=one_to_n,
            constructor_arguments=one_to_n_constructor_arguments,
            user_deposit_address=user_deposit.address,
            chain_id=chain_id,
        )
        return True


def _verify_user_deposit_deployment(
    user_deposit: Contract,
    constructor_arguments: List,
    token_address: Address,
    user_deposit_whole_balance_limit: int,
    one_to_n_address: Address,
    monitoring_service_address: Address,
):
    """ Check an onchain deployment of UserDeposit and constructor arguments at deployment time """
    assert len(constructor_arguments) == 2
    assert to_checksum_address(user_deposit.functions.token().call()) == token_address
    assert token_address == constructor_arguments[0]
    assert user_deposit.functions.whole_balance_limit().call() == user_deposit_whole_balance_limit
    assert user_deposit_whole_balance_limit == constructor_arguments[1]
    assert (
        to_checksum_address(user_deposit.functions.one_to_n_address().call()) == one_to_n_address
    )
    onchain_msc_address = to_checksum_address(user_deposit.functions.msc_address().call())
    assert onchain_msc_address == monitoring_service_address, (
        f"MSC address found onchain: {onchain_msc_address}, "
        f"expected: {monitoring_service_address}"
    )


def _verify_monitoring_service_deployment(
    monitoring_service: Contract,
    constructor_arguments: List,
    token_address: Address,
    service_registry_address: Address,
    user_deposit_address: Address,
) -> None:
    """ Check an onchain deployment of MonitoringService and constructor arguments """
    assert len(constructor_arguments) == 3
    assert to_checksum_address(monitoring_service.functions.token().call()) == token_address
    assert token_address == constructor_arguments[0]

    assert (
        to_checksum_address(monitoring_service.functions.service_registry().call())
        == service_registry_address
    )
    assert service_registry_address == constructor_arguments[1]

    assert (
        to_checksum_address(monitoring_service.functions.user_deposit().call())
        == user_deposit_address
    )
    assert user_deposit_address == constructor_arguments[2]


def _verify_one_to_n_deployment(
    one_to_n: Contract, constructor_arguments: List, user_deposit_address: Address, chain_id: int
) -> None:
    """ Check an onchain deployment of OneToN and constructor arguments """
    assert (
        to_checksum_address(one_to_n.functions.deposit_contract().call()) == user_deposit_address
    )
    assert user_deposit_address == constructor_arguments[0]
    assert chain_id == constructor_arguments[1]
    assert len(constructor_arguments) == 2


def _verify_service_registry_deployment(
    service_registry: Contract, constructor_arguments: List, token_address: Address
) -> None:
    """ Check an onchain deployment of ServiceRegistry and constructor arguments """
    assert to_checksum_address(service_registry.functions.token().call()) == token_address
    assert token_address == constructor_arguments[0]
    assert len(constructor_arguments) == 1
