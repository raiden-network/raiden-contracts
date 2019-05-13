"""ContractSourceManager knows the sources and how to compile them."""
import hashlib
import json
from os import chdir
from pathlib import Path
from typing import Dict

from solc import compile_files

from raiden_contracts.constants import PRECOMPILED_DATA_FIELDS, DeploymentModule
from raiden_contracts.contract_manager import ContractManager

_BASE = Path(__file__).parent


class ContractSourceManagerCompilationError(RuntimeError):
    """Compilation failed for infrastructural reasons (lack of the compiler,
    failure to take checksums)."""


class ContractSourceManagerVerificationError(RuntimeError):
    """Failure in comparing contracts.json contents against sources."""


class ContractSourceManager:
    """ ContractSourceManager knows how to compile contracts """

    def __init__(self, path: Dict[str, Path]) -> None:
        """ Parmas: a dictionary of directories which contain solidity files to compile """
        if not isinstance(path, dict):
            raise TypeError("Wrong type of argument given for ContractSourceManager()")
        self.contracts_source_dirs = path

    def _compile_all_contracts(self) -> Dict:
        """
        Compile solidity contracts into ABI and BIN. This requires solc somewhere in the $PATH
        and also the :ref:`ethereum.tools` python library.  The return value is a dict that
        should be written into contracts.json.
        """
        ret = {}
        old_working_dir = Path.cwd()
        chdir(_BASE)

        def relativise(path):
            return path.relative_to(_BASE)

        import_dir_map = [
            "%s=%s" % (k, relativise(v)) for k, v in self.contracts_source_dirs.items()
        ]
        import_dir_map.insert(0, ".=.")  # allow solc to compile contracts in all subdirs
        try:
            for contracts_dir in self.contracts_source_dirs.values():
                res = compile_files(
                    [str(relativise(file)) for file in contracts_dir.glob("*.sol")],
                    output_values=PRECOMPILED_DATA_FIELDS + ["ast"],
                    import_remappings=import_dir_map,
                    optimize=False,
                )

                # Strip `ast` part from result
                # TODO: Remove after https://github.com/ethereum/py-solc/issues/56 is fixed
                res = {
                    contract_name: {
                        content_key: content_value
                        for content_key, content_value in contract_content.items()
                        if content_key != "ast"
                    }
                    for contract_name, contract_content in res.items()
                }
                ret.update(_fix_contract_key_names(res))
        except FileNotFoundError as ex:
            raise ContractSourceManagerCompilationError(
                "Could not compile the contract. Check that solc is available."
            ) from ex
        finally:
            chdir(old_working_dir)
        return ret

    def compile_contracts(self, target_path: Path) -> ContractManager:
        """ Store compiled contracts JSON at `target_path`. """
        self.checksum_contracts()

        if self.overall_checksum is None:
            raise ContractSourceManagerCompilationError("Checksumming failed.")

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
        """ Compare source code checksums with those from a precompiled file

        Throws AttributeError if called before checksum_contracts(). """

        # We get the precompiled file data
        contracts_precompiled = ContractManager(precompiled_path)

        # Compare each contract source code checksum with the one from the precompiled file
        for contract, checksum in self.contracts_checksums.items():
            try:
                # Silence mypy
                assert contracts_precompiled.contracts_checksums is not None
                precompiled_checksum = contracts_precompiled.contracts_checksums[contract]
            except KeyError:
                raise ContractSourceManagerVerificationError(f"No checksum for {contract}")
            if precompiled_checksum != checksum:
                raise ContractSourceManagerVerificationError(
                    f"checksum of {contract} does not match {precompiled_checksum} != {checksum}"
                )

        # Compare the overall source code checksum with the one from the precompiled file
        if self.overall_checksum != contracts_precompiled.overall_checksum:
            raise ContractSourceManagerVerificationError(
                f"overall checksum does not match "
                f"{self.overall_checksum} != {contracts_precompiled.overall_checksum}"
            )

    def checksum_contracts(self) -> None:
        """Remember the checksum of each source, and the overall checksum."""
        checksums: Dict[str, str] = {}
        for contracts_dir in self.contracts_source_dirs.values():
            file: Path
            for file in contracts_dir.glob("*.sol"):
                checksums[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()

        self.overall_checksum = hashlib.sha256(
            ":".join(checksums[key] for key in sorted(checksums)).encode()
        ).hexdigest()
        self.contracts_checksums = checksums


def contracts_source_path():
    return contracts_source_path_with_stem("data/source")


def contracts_source_path_of_deployment_module(module: DeploymentModule):
    if module == DeploymentModule.RAIDEN:
        return contracts_source_path()["raiden"]
    elif module == DeploymentModule.SERVICES:
        return contracts_source_path()["services"]
    else:
        raise ValueError(f"No source known for module {module}")


def contracts_source_path_with_stem(stem):
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
