from typing import Dict

from web3.contract import ContractFunction


def call_and_transact(contract_function: ContractFunction, transaction_params: Dict) -> str:
    """ Executes contract_function.{call, transaction}(transaction_params) and returns txhash """
    # First 'call' might raise an exception
    contract_function.call(transaction_params)
    return contract_function.transact(transaction_params)
