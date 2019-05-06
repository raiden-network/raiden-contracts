import os
import stat
import tempfile

import pytest

from raiden_contracts.utils.private_key import check_permission_safety, get_private_key


def test_permission_safety_different_uid():
    """ check_permission_safety() should fail on a file with a different uid """
    assert not check_permission_safety("/")


def test_permission_safety_group_writable():
    """ check_permission_safety() should fail on a file that is writable to group """
    with tempfile.NamedTemporaryFile() as tmpfile:
        orig = os.stat(tmpfile.name).st_mode
        os.chmod(tmpfile.name, stat.S_IWGRP | orig)
        assert not check_permission_safety(tmpfile.name)


def test_permission_safety_executable():
    """ check_permission_safety() should fail on a file that is executable to others """
    with tempfile.NamedTemporaryFile() as tmpfile:
        orig = os.stat(tmpfile.name).st_mode
        os.chmod(tmpfile.name, stat.S_IXOTH | orig)
        assert not check_permission_safety(tmpfile.name)


def test_get_private_key_empty_path():
    """ get_private_key() should raise AssertionFailure on an empty key path """
    with pytest.raises(AssertionError):
        get_private_key("")


def test_get_private_key_nonexistent():
    """ get_private_key() should return None on a nonexistent file path """
    assert get_private_key("ggg") is None


def test_get_private_key_writable_keyfile():
    """ get_private_key() should return None on a key path with wrong permissions """
    with tempfile.NamedTemporaryFile() as tmpfile:
        orig = os.stat(tmpfile.name).st_mode
        os.chmod(tmpfile.name, stat.S_IWGRP | orig)
        assert get_private_key(tmpfile.name) is None


def test_get_private_key_writable_password_file():
    """ get_private_key() should return None on a password path with wrong permissions """
    with tempfile.NamedTemporaryFile() as keyfile:
        with tempfile.NamedTemporaryFile() as password_file:
            orig = os.stat(password_file.name).st_mode
            os.chmod(password_file.name, stat.S_IWGRP | orig)
            assert get_private_key(key_path=keyfile.name, password_path=password_file.name) is None
