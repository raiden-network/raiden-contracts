import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Optional


def load_json_from_path(f: Path) -> Optional[Dict[str, Any]]:
    try:
        with f.open() as deployment_file:
            return json.load(deployment_file)
    except FileNotFoundError:
        return None
    except (JSONDecodeError, UnicodeDecodeError) as ex:
        raise ValueError(f"Deployment data file is corrupted: {ex}") from ex
