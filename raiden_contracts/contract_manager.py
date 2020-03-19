"""ContractManager knows binaries and ABI of contracts."""
import json
from copy import deepcopy
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional

from eth_typing import HexStr
from eth_typing.evm import ChecksumAddress
from mypy_extensions import TypedDict
from web3.types import ABI, ABIEvent

from raiden_contracts.constants import ID_TO_CHAINNAME, DeploymentModule
from raiden_contracts.utils.file_ops import load_json_from_path
from raiden_contracts.utils.type_aliases import ChainID
from raiden_contracts.utils.versions import contracts_version_provides_services

_BASE = Path(__file__).parent


# Classes for static type checking of deployed_contracts dictionary.


CompiledContract = TypedDict(
    "CompiledContract", {"abi": ABI, "bin-runtime": str, "bin": str, "metadata": str},
)


DeployedContract = TypedDict(
    "DeployedContract",
    {
        "address": ChecksumAddress,
        "transaction_hash": HexStr,
        "block_number": int,
        "gas_cost": int,
        "constructor_arguments": List[Any],
    },
)


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
        try:
            with path.open() as precompiled_file:
                precompiled_content = json.load(precompiled_file)
        except (JSONDecodeError, UnicodeDecodeError) as ex:
            raise ContractManagerLoadError(f"Can't load precompiled smart contracts: {ex}") from ex
        try:
            self.contracts: Dict[str, CompiledContract] = precompiled_content["contracts"]
            if not self.contracts:
                raise RuntimeError(
                    f"Cannot find precompiled contracts data in the JSON file {path}."
                )
            self.overall_checksum = precompiled_content["overall_checksum"]
            self.contracts_checksums = precompiled_content["contracts_checksums"]
            self.contracts_version = precompiled_content["contracts_version"]
        except KeyError as ex:
            raise ContractManagerLoadError(
                f"Precompiled contracts json has unexpected format: {ex}"
            ) from ex

    def get_contract(self, contract_name: str) -> CompiledContract:
        """ Return ABI, BIN of the given contract. """
        assert self.contracts, "ContractManager should have contracts compiled"
        try:
            return self.contracts[contract_name]
        except KeyError:
            raise KeyError(
                f"contracts_version {self.contracts_version} does not have {contract_name}"
            )

    def has_contract(self, contract_name: str) -> bool:
        return contract_name in self.contracts

    def get_contract_abi(self, contract_name: str) -> ABI:
        """ Returns the ABI for a given contract. """
        assert self.contracts, "ContractManager should have contracts compiled"
        return self.contracts[contract_name]["abi"]

    def get_event_abi(self, contract_name: str, event_name: str) -> ABIEvent:
        """ Returns the ABI for a given event. """
        # Import locally to avoid web3 dependency during installation via `compile_contracts`
        from web3._utils.contracts import find_matching_event_abi

        assert self.contracts, "ContractManager should have contracts compiled"
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(abi=contract_abi, event_name=event_name)

    def get_constructor_argument_types(self, contract_name: str) -> List:
        abi = self.get_contract_abi(contract_name=contract_name)
        constructor = [f for f in abi if f["type"] == "constructor"][0]
        return [arg["type"] for arg in constructor["inputs"]]

    def get_runtime_hexcode(self, contract_name: str) -> str:
        """ Calculate the runtime hexcode with 0x prefix.

        Parameters:
            contract_name: name of the contract such as CONTRACT_TOKEN_NETWORK
        """
        return "0x" + self.contracts[contract_name]["bin-runtime"]


def contracts_data_path(version: Optional[str] = None) -> Path:
    """Returns the deployment data directory for a version."""
    if version is None:
        return _BASE.joinpath("data")
    return _BASE.joinpath(f"data_{version}")


def contracts_precompiled_path(version: Optional[str] = None) -> Path:
    """Returns the path of JSON file where the bytecode can be found."""
    data_path = contracts_data_path(version)
    return data_path.joinpath("contracts.json")


def contracts_gas_path(version: Optional[str] = None) -> Any:
    """Returns the path of JSON file where the gas usage information can be found."""
    data_path = contracts_data_path(version)
    return data_path.joinpath("gas.json")


def gas_measurements(version: Optional[str] = None) -> Dict[str, int]:
    """Returns gas usage measurement."""
    json_path = contracts_gas_path(version)
    with json_path.open() as gas_file:
        return json.load(gas_file)


def contracts_deployed_path(
    chain_id: ChainID, version: Optional[str] = None, services: bool = False
) -> Path:
    """Returns the path of the deplolyment data JSON file."""
    data_path = contracts_data_path(version)
    chain_name = ID_TO_CHAINNAME[chain_id] if chain_id in ID_TO_CHAINNAME else "private_net"

    return data_path.joinpath(f'deployment_{"services_" if services else ""}{chain_name}.json')


def merge_deployment_data(dict1: DeployedContracts, dict2: DeployedContracts) -> DeployedContracts:
    """ Take contents of two deployment JSON files and merge them

    The dictionary under 'contracts' key will be merged. The 'contracts'
    contents from different JSON files must not overlap. The contents
    under other keys must be identical.
    """
    if not dict1:
        return dict2
    if not dict2:
        return dict1
    common_contracts: Dict[str, DeployedContract] = deepcopy(dict1["contracts"])
    if common_contracts.keys() & dict2["contracts"].keys():
        raise ValueError(
            "dict1 and dict2 contain contracts of the same name. "
            "Now failing instead of overwriting any of these."
        )
    common_contracts.update(dict2["contracts"])

    if dict2["chain_id"] != dict1["chain_id"]:
        raise ValueError("Got dictionaries with different chain_id's.")
    if dict2["contracts_version"] != dict1["contracts_version"]:
        raise ValueError("Got dictionaries with different contracts_versions.")

    return DeployedContracts(
        {
            "contracts": common_contracts,
            "chain_id": dict1["chain_id"],
            "contracts_version": dict1["contracts_version"],
        }
    )


def get_contracts_deployment_info(
    chain_id: ChainID,
    version: Optional[str] = None,
    module: DeploymentModule = DeploymentModule.ALL,
) -> Optional[DeployedContracts]:
    """Reads the deployment data. Returns None if the file is not found.

    Parameter:
        module The name of the module. ALL means deployed contracts from all modules that are
        available for the version.
    """
    if not isinstance(module, DeploymentModule):
        raise ValueError(f"Unknown module {module} given to get_contracts_deployment_info()")

    def module_chosen(to_be_added: DeploymentModule) -> bool:
        return module == to_be_added or module == DeploymentModule.ALL

    files: List[Path] = []

    if module_chosen(DeploymentModule.RAIDEN):
        files.append(contracts_deployed_path(chain_id=chain_id, version=version, services=False))

    if module == DeploymentModule.SERVICES and not contracts_version_provides_services(version):
        raise ValueError(
            f"SERVICES module queried for version {version}, but {version} "
            "does not provide service contracts."
        )

    if module_chosen(DeploymentModule.SERVICES) and contracts_version_provides_services(version):
        files.append(contracts_deployed_path(chain_id=chain_id, version=version, services=True))

    deployment_data: DeployedContracts = {}  # type: ignore

    for f in files:
        j = load_json_from_path(f)
        if j is None:
            continue
        deployment_data = merge_deployment_data(
            deployment_data,
            DeployedContracts(
                {
                    "chain_id": j["chain_id"],
                    "contracts": j["contracts"],
                    "contracts_version": j["contracts_version"],
                }
            ),
        )

    if not deployment_data:
        deployment_data = None
    return deployment_data
