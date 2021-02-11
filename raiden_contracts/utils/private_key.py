import getpass
import json
import logging
import os
import stat
from pathlib import Path
from typing import Optional

from eth_keyfile import decode_keyfile_json
from eth_utils import decode_hex, is_hex

from raiden_contracts.utils.type_aliases import PrivateKey

log = logging.getLogger(__name__)

# This file was copied from
# https://github.com/raiden-network/raiden-libs/blob/9902dcdb74b8d18a232df3f1e1dc5442882419fe/raiden_libs/utils/private_key.py
# during the deprecation of raiden-lib.


def check_permission_safety(path: Path) -> bool:
    """Check if the file at the given path is safe to use as a state file.

    This checks that group and others have no permissions on the file and that the current user is
    the owner.
    """
    f_stats = os.stat(path)
    return (f_stats.st_mode & (stat.S_IRWXG | stat.S_IRWXO)) == 0 and f_stats.st_uid == os.getuid()


def get_private_key(key_path: Path, password_path: Optional[Path] = None) -> Optional[PrivateKey]:
    """Open a JSON-encoded private key and return it

    If a password file is provided, uses it to decrypt the key. If not, the
    password is asked interactively. Raw hex-encoded private keys are supported,
    but deprecated."""

    if not key_path:
        log.critical(f"key_path has to be something but got {key_path}")
        return None

    if not os.path.exists(key_path):
        log.critical("%s: no such file", key_path)
        return None

    if not check_permission_safety(key_path):
        log.critical("Private key file %s must be readable only by its owner.", key_path)
        return None

    if password_path and not check_permission_safety(password_path):
        log.critical("Password file %s must be readable only by its owner.", password_path)
        return None

    with open(key_path) as keyfile:
        raw_keyfile = keyfile.readline().strip()

        if is_hex(raw_keyfile) and len(decode_hex(raw_keyfile)) == 32:
            log.warning("Private key in raw format. Consider switching to JSON-encoded")
            return PrivateKey(decode_hex(raw_keyfile))
        else:
            keyfile.seek(0)
            try:
                json_data = json.load(keyfile)
                if password_path:
                    with open(password_path) as password_file:
                        password = password_file.readline().strip()
                else:
                    password = getpass.getpass("Enter the private key password: ")
                if json_data["crypto"]["kdf"] == "pbkdf2":
                    password = password.encode()  # type: ignore
                return PrivateKey(decode_keyfile_json(json_data, password))
            except ValueError:
                log.critical("Invalid private key format or password!")
                return None
