"""ContractManager knows binaries and ABI of contracts."""
import json
from copy import deepcopy
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List, Optional

from mypy_extensions import TypedDict
from semver import compare

from raiden_contracts.constants import CONTRACTS_VERSION, ID_TO_NETWORKNAME, DeploymentModule
from raiden_contracts.utils.type_aliases import Address

_BASE = Path(__file__).parent


# Classes for static type checking of deployed_contracts dictionary.


DeployedContract = TypedDict(
    "DeployedContract",
    {
        "address": Address,
        "transaction_hash": str,
        "block_number": int,
        "gas_cost": int,
        "constructor_arguments": List[Any],
        "abi": List[Dict[str, Any]],
        "bin-runtime": str,
        "bin": str,
        "metadata": str,
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
        self.overall_checksum = None
        self.contracts_checksums: Optional[Dict[str, str]] = None
        try:
            with path.open() as precompiled_file:
                precompiled_content = json.load(precompiled_file)
        except (JSONDecodeError, UnicodeDecodeError) as ex:
            raise ContractManagerLoadError(f"Can't load precompiled smart contracts: {ex}") from ex
        try:
            self.contracts: Dict[str, DeployedContract] = precompiled_content["contracts"]
            self.overall_checksum = precompiled_content["overall_checksum"]
            self.contracts_checksums = precompiled_content["contracts_checksums"]
            self.contracts_version = precompiled_content["contracts_version"]
        except KeyError as ex:
            raise ContractManagerLoadError(
                f"Precompiled contracts json has unexpected format: {ex}"
            ) from ex

    def get_contract(self, contract_name: str) -> DeployedContract:
        """ Return ABI, BIN of the given contract. """
        assert self.contracts, "ContractManager should have contracts compiled"
        try:
            return self.contracts[contract_name]
        except KeyError:
            raise KeyError(
                f"contracts_version {self.contracts_version} does not have {contract_name}"
            )

    def get_contract_abi(self, contract_name: str) -> List[Dict[str, Any]]:
        """ Returns the ABI for a given contract. """
        assert self.contracts, "ContractManager should have contracts compiled"
        return self.contracts[contract_name]["abi"]

    def get_event_abi(self, contract_name: str, event_name: str) -> Dict[str, Any]:
        """ Returns the ABI for a given event. """
        # Import locally to avoid web3 dependency during installation via `compile_contracts`
        from web3.utils.contracts import find_matching_event_abi

        assert self.contracts, "ContractManager should have contracts compiled"
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(abi=contract_abi, event_name=event_name)

    def get_constructor_argument_types(self, contract_name: str) -> List:
        abi = self.get_contract_abi(contract_name=contract_name)
        constructor = [f for f in abi if f["type"] == "constructor"][0]
        return [arg["type"] for arg in constructor["inputs"]]

    @property
    def version_string(self):
        """Return a flavored version string."""
        return contract_version_string(self.contracts_version)

    def get_runtime_hexcode(self, contract_name: str):
        """ Calculate the runtime hexcode with 0x prefix.

        Parameters:
            contract_name: name of the contract such as CONTRACT_TOKEN_NETWORK
        """
        return "0x" + self.contracts[contract_name]["bin-runtime"]


def contract_version_string(version: Optional[str] = None) -> str:
    """ The version string that should be found in the Solidity source """
    if version is None:
        version = CONTRACTS_VERSION
    return version


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


def contracts_deployed_path(
    chain_id: int, version: Optional[str] = None, services: bool = False
) -> Path:
    """Returns the path of the deplolyment data JSON file."""
    data_path = contracts_data_path(version)
    chain_name = ID_TO_NETWORKNAME[chain_id] if chain_id in ID_TO_NETWORKNAME else "private_net"

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
    assert not common_contracts.keys() & dict2["contracts"].keys()
    common_contracts.update(dict2["contracts"])

    assert dict2["chain_id"] == dict1["chain_id"]
    assert dict2["contracts_version"] == dict1["contracts_version"]

    return {
        "contracts": common_contracts,
        "chain_id": dict1["chain_id"],
        "contracts_version": dict1["contracts_version"],
    }


def version_provides_services(version: Optional[str]) -> bool:
    if version is None:
        return True
    if version == "0.3._":
        return False
    if version == "0.8.0_unlimited":
        return True
    return compare(version, "0.8.0") >= 0


def get_contracts_deployment_info(
    chain_id: int, version: Optional[str] = None, module: DeploymentModule = DeploymentModule.ALL
) -> Optional[DeployedContracts]:
    """Reads the deployment data. Returns None if the file is not found.

    Parameter:
        module The name of the module. ALL means deployed contracts from all modules that are
        available for the version.
    """
    if module not in DeploymentModule:
        raise ValueError(f"Unknown module {module} given to get_contracts_deployment_info()")

    def module_chosen(to_be_added: DeploymentModule):
        return module == to_be_added or module == DeploymentModule.ALL

    files: List[Path] = []

    if module_chosen(DeploymentModule.RAIDEN):
        files.append(contracts_deployed_path(chain_id=chain_id, version=version, services=False))

    if module == DeploymentModule.SERVICES and not version_provides_services(version):
        raise ValueError(
            f"SERVICES module queried for version {version}, but {version} "
            "does not provide service contracts."
        )

    if module_chosen(DeploymentModule.SERVICES) and version_provides_services(version):
        files.append(contracts_deployed_path(chain_id=chain_id, version=version, services=True))

    deployment_data: DeployedContracts = {}  # type: ignore

    for f in files:
        j = _load_json_from_path(f)
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


def _load_json_from_path(f: Path) -> Optional[Dict[str, Any]]:
    try:
        with f.open() as deployment_file:
            return json.load(deployment_file)
    except FileNotFoundError:
        return None
    except (JSONDecodeError, UnicodeDecodeError) as ex:
        raise ValueError(f"Deployment data file is corrupted: {ex}") from ex
