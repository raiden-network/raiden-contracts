from typing import Optional

import pytest

from raiden_contracts.constants import CONTRACTS_VERSION
from raiden_contracts.contract_manager import contracts_data_path


@pytest.mark.parametrize("version", [None, CONTRACTS_VERSION])
def test_deploy_data_dir_exists(version: Optional[str]):
    assert contracts_data_path(version).exists(), "deployment data does not exist"
