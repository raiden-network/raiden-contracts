from logging import getLogger
from typing import Optional

from eth_utils import denoms, encode_hex, is_address, to_checksum_address
from web3 import Web3
from web3.contract import ContractFunction
from web3.middleware import construct_sign_and_send_raw_middleware

from raiden_contracts.constants import CONTRACTS_VERSION
from raiden_contracts.contract_manager import contract_version_string
from raiden_contracts.contract_source_manager import ContractSourceManager, contracts_source_path
from raiden_contracts.deploy.contract_verifyer import ContractVerifyer
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.transaction import check_successful_tx

LOG = getLogger(__name__)


class ContractDeployer(ContractVerifyer):
    def __init__(
            self,
            web3: Web3,
            private_key: str,
            gas_limit: int,
            gas_price: int=1,
            wait: int=10,
            contracts_version: Optional[str]=None,
    ):
        # pylint: disable=E1101
        super(ContractDeployer, self).__init__(web3=web3, contracts_version=contracts_version)
        self.wait = wait
        self.owner = private_key_to_address(private_key)
        self.transaction = {'from': self.owner, 'gas': gas_limit}
        if gas_price != 0:
            self.transaction['gasPrice'] = gas_price * denoms.gwei

        self.web3.middleware_stack.add(
            construct_sign_and_send_raw_middleware(private_key),
        )

        # Check that the precompiled data matches the source code
        # Only for current version, because this is the only one with source code
        if self.contracts_version in [None, CONTRACTS_VERSION]:
            contract_manager_source = ContractSourceManager(contracts_source_path())
            contract_manager_source.checksum_contracts()
            contract_manager_source.verify_precompiled_checksums(self.precompiled_path)
        else:
            LOG.info('Skipped checks against the source code because it is not available.')

    def deploy(
            self,
            contract_name: str,
            args=None,
    ):
        if args is None:
            args = list()
        contract_interface = self.contract_manager.get_contract(
            contract_name,
        )

        # Instantiate and deploy contract
        contract = self.web3.eth.contract(
            abi=contract_interface['abi'],
            bytecode=contract_interface['bin'],
        )

        # Get transaction hash from deployed contract
        txhash = self.send_deployment_transaction(
            contract=contract,
            args=args,
        )

        # Get tx receipt to get contract address
        LOG.debug(
            f'Deploying {contract_name} txHash={encode_hex(txhash)}, '
            f'contracts version {self.contract_manager.contracts_version}',
        )
        (receipt, tx) = check_successful_tx(
            web3=self.web3,
            txid=txhash,
            timeout=self.wait,
        )
        if not receipt['contractAddress']:  # happens with Parity
            receipt = dict(receipt)
            receipt['contractAddress'] = tx['creates']
        LOG.info(
            '{0} address: {1}. Gas used: {2}'.format(
                contract_name,
                receipt['contractAddress'],
                receipt['gasUsed'],
            ),
        )
        return receipt

    def transact(
            self,
            contract_method: ContractFunction,
    ):
        """ A wrapper around to_be_called.transact() that waits until the transaction succeeds. """
        txhash = contract_method.transact(self.transaction)
        LOG.debug(f'Sending txHash={encode_hex(txhash)}')
        (receipt, _) = check_successful_tx(
            web3=self.web3,
            txid=txhash,
            timeout=self.wait,
        )
        return receipt

    def send_deployment_transaction(self, contract, args):
        txhash = None
        while txhash is None:
            try:
                txhash = contract.constructor(*args).transact(
                    self.transaction,
                )
            except ValueError as ex:
                # pylint: disable=E1126
                if ex.args[0]['code'] == -32015:
                    LOG.info(f'Deployment failed with {ex}. Retrying...')
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
            token_type: str = 'CustomToken',
    ):
        """Deploy a token contract."""
        receipt = self.deploy(
            contract_name=token_type,
            args=[token_supply, token_decimals, token_name, token_symbol],
        )
        token_address = receipt['contractAddress']
        assert token_address and is_address(token_address)
        token_address = to_checksum_address(token_address)
        return {token_type: token_address}
