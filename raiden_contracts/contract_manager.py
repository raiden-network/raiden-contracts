"""ContractManager knows binaries and ABI of contracts."""
import json
from copy import deepcopy
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional

from deprecated import deprecated
from mypy_extensions import TypedDict

from raiden_contracts.constants import CONTRACTS_VERSION, ID_TO_NETWORKNAME
from raiden_contracts.utils.type_aliases import Address

_BASE = Path(__file__).parent


# Classes for static type checking of deployed_contracts dictionary.


class DeployedContract(TypedDict):
    address: Address
    transaction_hash: str
    block_number: int
    gas_cost: int
    constructor_arguments: Any


class DeployedContracts(TypedDict):
    chain_id: int
    contracts: Dict[str, DeployedContract]
    contracts_version: str


class ContractManagerLoadError(RuntimeError):
    """Failure in loading contracts.json."""


class ContractManager:
    """ ContractManager holds compiled contracts of the same version

    Provides access to the ABI and the bytecode.
    """
    def __init__(self, path: Path) -> None:
        """Params:
            path: path to a precompiled contract JSON file,
        """
        self.overall_checksum = None
        self.contracts_checksums: Optional[Dict[str, str]] = None
        try:
            with path.open() as precompiled_file:
                precompiled_content = json.load(precompiled_file)
        except (JSONDecodeError, UnicodeDecodeError) as ex:
            raise ContractManagerLoadError(
                f"Can't load precompiled smart contracts: {ex}",
            ) from ex
        try:
            self.contracts = precompiled_content['contracts']
            self.overall_checksum = precompiled_content['overall_checksum']
            self.contracts_checksums = precompiled_content['contracts_checksums']
            self.contracts_version = precompiled_content['contracts_version']
        except KeyError as ex:
            raise ContractManagerLoadError(
                f'Precompiled contracts json has unexpected format: {ex}',
            ) from ex

    def get_contract(self, contract_name: str) -> Dict:
        """ Return ABI, BIN of the given contract. """
        assert self.contracts, 'ContractManager should have contracts compiled'
        return self.contracts[contract_name]

    def get_contract_abi(self, contract_name: str) -> Dict:
        """ Returns the ABI for a given contract. """
        assert self.contracts, 'ContractManager should have contracts compiled'
        return self.contracts[contract_name]['abi']

    def get_event_abi(self, contract_name: str, event_name: str) -> Dict:
        """ Returns the ABI for a given event. """
        # Import locally to avoid web3 dependency during installation via `compile_contracts`
        from web3.utils.contracts import find_matching_event_abi

        assert self.contracts, 'ContractManager should have contracts compiled'
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(contract_abi, event_name)

    def version_string(self):
        """Return a flavored version string."""
        return contract_version_string(self.contracts_version)


def contract_version_string(version: Optional[str] = None):
    """ The version string that should be found in the Solidity source """
    if version is None:
        version = CONTRACTS_VERSION
    return version


def contracts_data_path(version: Optional[str] = None):
    """Returns the deployment data directory for a version."""
    if version is None:
        return _BASE.joinpath('data')
    return _BASE.joinpath(f'data_{version}')


def contracts_precompiled_path(version: Optional[str] = None) -> Path:
    """Returns the path of JSON file where the bytecode can be found."""
    data_path = contracts_data_path(version)
    return data_path.joinpath('contracts.json')


def contracts_gas_path(version: Optional[str] = None):
    """Returns the path of JSON file where the gas usage information can be found."""
    data_path = contracts_data_path(version)
    return data_path.joinpath('gas.json')


def contracts_deployed_path(
        chain_id: int,
        version: Optional[str] = None,
        services: bool = False,
):
    """Returns the path of the deplolyment data JSON file."""
    data_path = contracts_data_path(version)
    chain_name = ID_TO_NETWORKNAME[chain_id] if chain_id in ID_TO_NETWORKNAME else 'private_net'

    return data_path.joinpath(f'deployment_{"services_" if services else ""}{chain_name}.json')


class DeploymentModule(Enum):
    RAIDEN = 'raiden'
    SERVICES = 'services'
    ALL = 'all'


@deprecated(reason='Use get_contract_deployment_info()')
def get_contracts_deployed(
        chain_id: int,
        version: Optional[str] = None,
        services: bool = False,
) -> Dict:
    """Reads the deployment data."""
    return get_contracts_deployment_info(
        chain_id=chain_id,
        version=version,
        module=DeploymentModule.SERVICES if services else DeploymentModule.RAIDEN,
    )


def merge_deployment_data(dict1: Dict, dict2: Dict) -> Dict:
    """ Take contents of two deployment JSON files and merge them

    The dictionary under 'contracts' key will be merged. The 'contracts'
    contents from different JSON files must not overlap. The contents
    under other keys must be identical.
    """
    if not dict1:
        return dict2
    if not dict2:
        return dict1
    result = {}
    for k1, v1 in dict1.items():
        if k1 == 'contracts':
            v: DeployedContracts = deepcopy(v1)
            # If keys overlap, we would be overwriing some contents away.
            assert not v.keys() & dict2['contracts'].keys()
            v.update(dict2['contracts'])
            result['contracts'] = v
        else:
            assert dict2[k1] == v1
            result[k1] = v1
    return result


def get_contracts_deployment_info(
        chain_id: int,
        version: Optional[str] = None,
        module: DeploymentModule = DeploymentModule.ALL,
) -> Dict:
    """Reads the deployment data.

    Parameter:
        module The name of the module. ALL means deployed contracts from all modules.
    """
    if module not in DeploymentModule:
        raise ValueError(f'Unknown module {module} given to get_contracts_deployment_info()')

    files: List[Path] = []

    if module == DeploymentModule.RAIDEN or module == DeploymentModule.ALL:
        files.append(contracts_deployed_path(
            chain_id=chain_id,
            version=version,
            services=False,
        ))

    if module == DeploymentModule.SERVICES or module == DeploymentModule.ALL:
        files.append(contracts_deployed_path(
            chain_id=chain_id,
            version=version,
            services=True,
        ))

    deployment_data: Dict = {}

    for f in files:
        try:
            with f.open() as deployment_file:
                deployment_data = merge_deployment_data(
                    deployment_data,
                    json.load(deployment_file),
                )
        except (JSONDecodeError, UnicodeDecodeError, FileNotFoundError) as ex:
            raise ValueError(f'Cannot load deployment data file: {ex}') from ex
    return deployment_data
