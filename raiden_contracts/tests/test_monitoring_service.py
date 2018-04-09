import pytest

@pytest.mark.xfail(reason='fixture initialization fails')
def test_msc_happy_path(monitoring_service_external):
    # 1) open a channel (c1, c2)
    # 2) create balance proof for c1
    # 3) c2 closes channel
    # 4) MS calls updateTransfer with MSC & c1's BP
    # 5) MSC calls TokenNetwork updateTransfer
    # 6) channel is settled
    # 7) MS claims the reward
    pass
