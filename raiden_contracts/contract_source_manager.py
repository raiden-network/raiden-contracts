"""ContractSourceManager knows the sources and how to compile them."""
import hashlib
import json
from os import chdir
from pathlib import Path
from typing import Dict, Optional, Tuple

import solcx

from raiden_contracts.constants import PRECOMPILED_DATA_FIELDS, DeploymentModule
from raiden_contracts.contract_manager import ContractManager, contracts_data_path

_BASE = Path(__file__).parent
SOLC_VERSION = "0.8.7"


class ContractSourceManagerCompilationError(RuntimeError):
    """Compilation failed for infrastructural reasons (lack of the compiler,
    failure to take checksums)."""


class ContractSourceManagerVerificationError(RuntimeError):
    """Failure in comparing contracts.json contents against sources."""


class ContractSourceManager:
    """ContractSourceManager knows how to compile contracts"""

    def __init__(self, path: Dict[str, Path]) -> None:
        """Params: path: a dictionary of directories which contain solidity files to compile"""
        if not isinstance(path, dict):
            raise TypeError("Wrong type of argument given for ContractSourceManager()")
        self.contracts_source_dirs = path
        (self.contracts_checksums, self.overall_checksum) = self._checksum_contracts()

    def _compile_all_contracts(self) -> Dict:
        """
        Compile solidity contracts into ABI and BIN. This requires solc somewhere in the $PATH
        and also the :ref:`ethereum.tools` python library.  The return value is a dict that
        should be written into contracts.json.
        """
        solcx.install.install_solc(SOLC_VERSION)
        solcx.set_solc_version(SOLC_VERSION)
        ret = {}
        old_working_dir = Path.cwd()
        chdir(_BASE)

        def relativise(path: Path) -> Path:
            return path.relative_to(_BASE)

        import_dir_map = [
            "%s=%s" % (k, relativise(v)) for k, v in self.contracts_source_dirs.items()
        ]
        import_dir_map.insert(0, ".=.")  # allow solc to compile contracts in all subdirs
        try:
            for contracts_dir in self.contracts_source_dirs.values():
                res = solcx.compile_files(
                    [str(relativise(file)) for file in contracts_dir.glob("*.sol")],
                    output_values=PRECOMPILED_DATA_FIELDS,
                    import_remappings=import_dir_map,
                    optimize=True,
                    optimize_runs=200,
                )

                ret.update(_fix_contract_key_names(res))
        except FileNotFoundError as ex:
            raise ContractSourceManagerCompilationError(
                "Could not compile the contract. Check that solc is available."
            ) from ex
        finally:
            chdir(old_working_dir)
        check_runtime_codesize(ret)
        return ret

    def compile_contracts(self, target_path: Path) -> ContractManager:
        """Store compiled contracts JSON at `target_path`."""
        assert self.overall_checksum is not None

        contracts_compiled = self._compile_all_contracts()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open(mode="w") as target_file:
            target_file.write(
                json.dumps(
                    dict(
                        contracts=contracts_compiled,
                        contracts_checksums=self.contracts_checksums,
                        overall_checksum=self.overall_checksum,
                        contracts_version=None,
                    ),
                    sort_keys=True,
                    indent=4,
                )
            )

        return ContractManager(target_path)

    def verify_precompiled_checksums(self, precompiled_path: Path) -> None:
        """Compare source code checksums with those from a precompiled file

        If `contract_name` is None, all contracts checksums and the overall checksum are checked.
        """

        # We get the precompiled file data
        contracts_precompiled = ContractManager(precompiled_path)

        # Compare each contract source code checksum with the one from the precompiled file
        for contract, checksum in self.contracts_checksums.items():
            _verify_single_precompiled_checksum(
                checked_checksums=contracts_precompiled.contracts_checksums,
                contract_name=contract,
                expected_checksum=checksum,
            )

        # Compare the overall source code checksum with the one from the precompiled file
        if self.overall_checksum != contracts_precompiled.overall_checksum:
            raise ContractSourceManagerVerificationError(
                f"overall checksum does not match "
                f"{self.overall_checksum} != {contracts_precompiled.overall_checksum}"
            )

    def _checksum_contracts(self) -> Tuple[Dict[str, str], str]:
        """Compute the checksum of each source, and the overall checksum

        Returns (contracts_checksums, overall_checksum)
        """
        checksums: Dict[str, str] = {}
        for contracts_dir in self.contracts_source_dirs.values():
            file: Path
            for file in contracts_dir.glob("*.sol"):
                checksums[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()

        overall_checksum = hashlib.sha256(
            ":".join(checksums[key] for key in sorted(checksums)).encode()
        ).hexdigest()
        return (checksums, overall_checksum)


def contracts_source_path(contracts_version: Optional[str]) -> Dict[str, Path]:
    data = contracts_data_path(contracts_version)
    return contracts_source_path_with_stem(data.joinpath("source"))


def contracts_source_path_of_deployment_module(module: DeploymentModule) -> Path:
    if module == DeploymentModule.RAIDEN:
        return contracts_source_path(contracts_version=None)["raiden"]
    elif module == DeploymentModule.SERVICES:
        return contracts_source_path(contracts_version=None)["services"]
    else:
        raise ValueError(f"No source known for module {module}")


def contracts_source_path_with_stem(stem: Path) -> Dict[str, Path]:
    """The directory remapping given to the Solidity compiler."""
    return {
        "lib": _BASE.joinpath(stem, "lib"),
        "raiden": _BASE.joinpath(stem, "raiden"),
        "test": _BASE.joinpath(stem, "test"),
        "services": _BASE.joinpath(stem, "services"),
    }


def _fix_contract_key_names(d: Dict) -> Dict:
    result = {}

    for k, v in d.items():
        name = k.split(":")[1]
        result[name] = v

    return result


def check_runtime_codesize(d: Dict) -> None:
    """Raises a RuntimeError if the runtime codesize exceeds the EIP-170 limit"""
    for name, compilation in d.items():
        runtime_code_len = len(compilation["bin-runtime"]) // 2
        if runtime_code_len > 0x6000:
            raise RuntimeError(f"{name}'s runtime code is too big ({runtime_code_len} bytes).")


def _verify_single_precompiled_checksum(
    checked_checksums: Dict[str, str], contract_name: str, expected_checksum: str
) -> None:
    """Get `checked_checksums[contract_name]` and compare it against `expected_checksum`"""
    try:
        precompiled_checksum = checked_checksums[contract_name]
    except KeyError:
        raise ContractSourceManagerVerificationError(f"No checksum for {contract_name}")
    if precompiled_checksum != expected_checksum:
        raise ContractSourceManagerVerificationError(
            f"checksum of {contract_name} does not match. got {precompiled_checksum} != "
            f"expected {expected_checksum}"
        )


def verify_single_precompiled_checksum_on_nonexistent_contract_name() -> None:
    """A functiohn for testing the case where the contract name is not found"""
    _verify_single_precompiled_checksum(
        checked_checksums={}, contract_name="a", expected_checksum="abc"
    )
