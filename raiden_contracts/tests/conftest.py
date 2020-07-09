"""
isort:skip_file
"""
from pytest import register_assert_rewrite

register_assert_rewrite("raiden_contracts.utils.events")
register_assert_rewrite("raiden_contracts.tests.fixtures.channel")

from .fixtures import *  # noqa: F401,F403
