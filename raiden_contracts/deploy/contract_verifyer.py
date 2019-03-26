import json
from typing import Optional

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
)
from raiden_contracts.contract_manager import (
    ContractManager,
    DeployedContracts,
    contracts_deployed_path,
    contracts_precompiled_path,
    get_contracts_deployed,
)
from raiden_contracts.utils.bytecode import runtime_hexcode


class ContractVerifyer:
    def __init__(
            self,
            web3: Web3,
            contracts_version: Optional[str]=None,
    ):
        self.web3 = web3
        self.contracts_version = contracts_version
        self.precompiled_path = contracts_precompiled_path(self.contracts_version)
        self.contract_manager = ContractManager(self.precompiled_path)

    def verify_deployed_contracts_in_filesystem(self):
        chain_id = int(self.web3.version.network)

        deployment_data = get_contracts_deployed(
            chain_id=chain_id,
            version=self.contract_manager.contracts_version,
        )
        deployment_file_path = contracts_deployed_path(
            chain_id=chain_id,
            version=self.contract_manager.contracts_version,
        )
        assert deployment_data is not None

        if self._verify_deployment_data(deployment_data):
            print(f'Deployment info from {deployment_file_path} has been verified'
                  'and it is CORRECT.')

    def verify_deployed_service_contracts_in_filesystem(
            self,
            token_address: str,
            user_deposit_whole_balance_limit: int,
    ):
        chain_id = int(self.web3.version.network)

        deployment_data = get_contracts_deployed(
            chain_id=chain_id,
            version=self.contract_manager.contracts_version,
            services=True,
        )
        deployment_file_path = contracts_deployed_path(
            chain_id=chain_id,
            version=self.contract_manager.contracts_version,
            services=True,
        )
        assert deployment_data is not None

        if self._verify_service_contracts_deployment_data(
                token_address=token_address,
                user_deposit_whole_balance_limit=user_deposit_whole_balance_limit,
                deployment_data=deployment_data,
        ):
            print(f'Deployment info from {deployment_file_path} has been verified '
                  'and it is CORRECT.')

    def store_and_verify_deployment_info_raiden(
            self,
            deployed_contracts_info: DeployedContracts,
            save_info: bool,
    ):
        if save_info:
            self._store_deployment_info(
                deployment_info=deployed_contracts_info,
                services=False,
            )
            self.verify_deployed_contracts_in_filesystem()
        else:
            self._verify_deployment_data(deployed_contracts_info)

    def store_and_verify_deployment_info_services(
            self,
            deployed_contracts_info: DeployedContracts,
            save_info: bool,
            token_address: str,
            user_deposit_whole_limit: int,
    ):
        if save_info:
            self._store_deployment_info(
                services=True,
                deployment_info=deployed_contracts_info,
            )
            self.verify_deployed_service_contracts_in_filesystem(
                token_address=token_address,
                user_deposit_whole_balance_limit=user_deposit_whole_limit,
            )
        else:
            self._verify_service_contracts_deployment_data(
                token_address=token_address,
                user_deposit_whole_balance_limit=user_deposit_whole_limit,
                deployment_data=deployed_contracts_info,
            )

    def _store_deployment_info(
            self,
            services: bool,
            deployment_info: DeployedContracts,
    ):
        deployment_file_path = contracts_deployed_path(
            chain_id=int(self.web3.version.network),
            version=self.contracts_version,
            services=services,
        )
        with deployment_file_path.open(mode='w') as target_file:
            target_file.write(json.dumps(deployment_info))

        print(
            f'Deployment information for chain id = {deployment_info["chain_id"]} '
            f' has been updated at {deployment_file_path}.',
        )

    def _verify_deployment_data(
            self,
            deployment_data: DeployedContracts,
    ):
        chain_id = int(self.web3.version.network)
        assert deployment_data is not None

        assert self.contract_manager.version_string() == deployment_data['contracts_version']
        assert chain_id == deployment_data['chain_id']

        self._verify_deployed_contract(
            deployment_data=deployment_data,
            contract_name=CONTRACT_ENDPOINT_REGISTRY,
        )

        secret_registry, _ = self._verify_deployed_contract(
            deployment_data=deployment_data,
            contract_name=CONTRACT_SECRET_REGISTRY,
        )

        token_network_registry, constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployment_data,
            contract_name=CONTRACT_TOKEN_NETWORK_REGISTRY,
        )

        # We need to also check the constructor parameters against the chain
        assert to_checksum_address(
            token_network_registry.functions.secret_registry_address().call(),
        ) == secret_registry.address
        assert secret_registry.address == constructor_arguments[0]
        assert token_network_registry.functions.chain_id().call() == constructor_arguments[1]
        assert token_network_registry.functions.settlement_timeout_min().call() == \
            constructor_arguments[2]
        assert token_network_registry.functions.settlement_timeout_max().call() == \
            constructor_arguments[3]

        return True

    def _verify_deployed_contract(
            self,
            deployment_data: DeployedContracts,
            contract_name: str,
    ) -> Contract:
        """ Verify deployment info against the chain

        Verifies:
        - the runtime bytecode - precompiled data against the chain
        - information stored in deployment_*.json against the chain,
        except for the constructor arguments, which have to be checked
        separately.

        Returns: (onchain_instance, constructor_arguments)
        """
        contracts = deployment_data['contracts']

        contract_address = contracts[contract_name]['address']
        contract_instance = self.web3.eth.contract(
            abi=self.contract_manager.get_contract_abi(contract_name),
            address=contract_address,
        )

        # Check that the deployed bytecode matches the precompiled data
        blockchain_bytecode = self.web3.eth.getCode(contract_address).hex()
        compiled_bytecode = runtime_hexcode(
            contracts_manager=self.contract_manager,
            name=contract_name,
        )
        assert blockchain_bytecode == compiled_bytecode

        print(
            f'{contract_name} at {contract_address} '
            f'matches the compiled data from contracts.json',
        )

        # Check blockchain transaction hash & block information
        receipt = self.web3.eth.getTransactionReceipt(
            contracts[contract_name]['transaction_hash'],
        )
        assert receipt['blockNumber'] == contracts[contract_name]['block_number'], (
            f'We have block_number {contracts[contract_name]["block_number"]} '
            f'instead of {receipt["blockNumber"]}'
        )
        assert receipt['gasUsed'] == contracts[contract_name]['gas_cost'], (
            f'We have gasUsed {contracts[contract_name]["gas_cost"]} '
            f'instead of {receipt["gasUsed"]}'
        )
        assert receipt['contractAddress'] == contracts[contract_name]['address'], (
            f'We have contractAddress {contracts[contract_name]["address"]} '
            f'instead of {receipt["contractAddress"]}'
        )

        # Check the contract version
        version = contract_instance.functions.contract_version().call()
        assert version == deployment_data['contracts_version'], \
            f'got {version} expected {deployment_data["contracts_version"]}.' \
            f'contract_manager has contracts_version {self.contract_manager.contracts_version}'

        return contract_instance, contracts[contract_name]['constructor_arguments']

    def _verify_service_contracts_deployment_data(
            self,
            token_address: str,
            user_deposit_whole_balance_limit: int,
            deployment_data: DeployedContracts,
    ):
        chain_id = int(self.web3.version.network)
        assert deployment_data is not None

        assert self.contract_manager.version_string() == deployment_data['contracts_version']
        assert chain_id == deployment_data['chain_id']

        service_bundle, constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployment_data,
            contract_name=CONTRACT_SERVICE_REGISTRY,
        )
        assert to_checksum_address(service_bundle.functions.token().call()) == token_address
        assert token_address == constructor_arguments[0]

        user_deposit, constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployment_data,
            contract_name=CONTRACT_USER_DEPOSIT,
        )
        assert len(constructor_arguments) == 2
        assert to_checksum_address(user_deposit.functions.token().call()) == token_address
        assert token_address == constructor_arguments[0]
        assert user_deposit.functions.whole_balance_limit().call() == \
            user_deposit_whole_balance_limit
        assert user_deposit_whole_balance_limit == constructor_arguments[1]

        monitoring_service, constructor_arguments = self._verify_deployed_contract(
            deployment_data,
            CONTRACT_MONITORING_SERVICE,
        )
        assert len(constructor_arguments) == 3
        assert to_checksum_address(monitoring_service.functions.token().call()) == token_address
        assert token_address == constructor_arguments[0]

        assert to_checksum_address(
            monitoring_service.functions.service_registry().call(),
        ) == service_bundle.address
        assert service_bundle.address == constructor_arguments[1]

        assert to_checksum_address(
            monitoring_service.functions.user_deposit().call(),
        ) == user_deposit.address
        assert user_deposit.address == constructor_arguments[2]

        one_to_n, constructor_arguments = self._verify_deployed_contract(
            deployment_data=deployment_data,
            contract_name=CONTRACT_ONE_TO_N,
        )
        assert to_checksum_address(
            one_to_n.functions.deposit_contract().call(),
        ) == user_deposit.address
        assert user_deposit.address == constructor_arguments[0]
        assert len(constructor_arguments) == 1

        # Check that UserDeposit.init() had the right effect
        onchain_msc_address = to_checksum_address(user_deposit.functions.msc_address().call())
        assert onchain_msc_address == monitoring_service.address, \
            f'MSC address found onchain: {onchain_msc_address}, ' \
            f'expected: {monitoring_service.address}'
        assert to_checksum_address(
            user_deposit.functions.one_to_n_address().call(),
        ) == one_to_n.address

        return True
