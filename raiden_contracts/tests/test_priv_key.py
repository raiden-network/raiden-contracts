import os
import stat
import tempfile
from pathlib import Path

from raiden_contracts.utils.private_key import check_permission_safety, get_private_key


def test_permission_safety_different_uid() -> None:
    """ check_permission_safety() should fail on a file with a different uid """
    assert not check_permission_safety(Path("/"))


def test_permission_safety_group_writable() -> None:
    """ check_permission_safety() should fail on a file that is writable to group """
    with tempfile.NamedTemporaryFile() as tmpfile:
        orig = os.stat(tmpfile.name).st_mode
        os.chmod(tmpfile.name, stat.S_IWGRP | orig)
        assert not check_permission_safety(Path(tmpfile.name))


def test_permission_safety_executable() -> None:
    """ check_permission_safety() should fail on a file that is executable to others """
    with tempfile.NamedTemporaryFile() as tmpfile:
        orig = os.stat(tmpfile.name).st_mode
        os.chmod(tmpfile.name, stat.S_IXOTH | orig)
        assert not check_permission_safety(Path(tmpfile.name))


def test_get_private_key_empty_path() -> None:
    """ get_private_key() should return None on a None key path """
    assert get_private_key(None) is None  # type: ignore


def test_get_private_key_nonexistent() -> None:
    """ get_private_key() should return None on a nonexistent file path """
    assert get_private_key(Path("ggg")) is None


def test_get_private_key_writable_keyfile() -> None:
    """ get_private_key() should return None on a key path with wrong permissions """
    with tempfile.NamedTemporaryFile() as tmpfile:
        orig = os.stat(tmpfile.name).st_mode
        os.chmod(tmpfile.name, stat.S_IWGRP | orig)
        assert get_private_key(Path(tmpfile.name)) is None


def test_get_private_key_writable_password_file() -> None:
    """ get_private_key() should return None on a password path with wrong permissions """
    with tempfile.NamedTemporaryFile() as keyfile:
        with tempfile.NamedTemporaryFile() as password_file:
            orig = os.stat(password_file.name).st_mode
            os.chmod(password_file.name, stat.S_IWGRP | orig)
            assert (
                get_private_key(
                    key_path=Path(keyfile.name), password_path=Path(password_file.name)
                )
                is None
            )
