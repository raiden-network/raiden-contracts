import functools
from collections import defaultdict, namedtuple
from inspect import getframeinfo, stack
from typing import Any, Callable, Dict, List, Optional, cast

from click import echo
from eth_typing.evm import BlockNumber, ChecksumAddress, HexAddress
from eth_utils import to_checksum_address
from web3 import Web3
from web3._utils.events import get_event_data
from web3._utils.filters import LogFilter as Web3LogFilter, construct_event_filter_params
from web3._utils.threads import Timeout

# A concrete event added in a transaction.
from web3.types import ABI, ABIEvent, BlockIdentifier

LogRecorded = namedtuple("LogRecorded", "message callback count")
GenesisBlock = BlockNumber(0)


class LogHandler:
    def __init__(self, web3: Web3, address: HexAddress, abi: ABI):
        self.web3 = web3
        self.address = address
        self.abi = abi
        self.event_waiting: Dict[str, Dict[str, LogRecorded]] = {}
        self.event_filters: Dict[str, LogFilter] = {}
        self.event_count: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(lambda: 0))
        self.event_unknown: List[Dict[str, Any]] = []

    def add(
        self,
        txn_hash: str,
        event_name: str,
        callback: Optional[Callable[..., Any]] = None,
        count: int = 1,
    ) -> None:
        caller = getframeinfo(stack()[1][0])
        message = "%s:%d" % (caller.filename, caller.lineno)

        if event_name not in self.event_waiting:
            self.event_waiting[event_name] = {}
            self.event_filters[event_name] = LogFilter(
                web3=self.web3,
                abi=self.abi,
                address=to_checksum_address(self.address),
                event_name=event_name,
                callback=self.handle_log,
            )

        self.event_waiting[event_name][txn_hash] = LogRecorded(
            message=message, callback=callback, count=count
        )

    def check(self, timeout: int = 5) -> None:
        for event in list(self.event_filters.keys()):
            self.event_filters[event].init()

        self.wait(timeout)

    def _handle_waited_log(self, event: Dict[str, Any]) -> None:
        """A subroutine of handle_log
        Increment self.event_count, forget about waiting, and call the callback if any.
        """
        txn_hash = event["transactionHash"]
        event_name = event["event"]
        assert event_name in self.event_waiting
        assert txn_hash in self.event_waiting[event_name]

        self.event_count[event_name][txn_hash] += 1
        event_entry = self.event_waiting[event_name][txn_hash]

        if event_entry.count == self.event_count[event_name][txn_hash]:
            self.event_waiting[event_name].pop(txn_hash)

        # Call callback function with event
        if event_entry.callback:
            event_entry.callback(event)

    def handle_log(self, event: Dict[str, Any]) -> None:
        txn_hash = event["transactionHash"]
        event_name = event["event"]

        if event_name in self.event_waiting:
            if txn_hash in self.event_waiting[event_name]:
                self._handle_waited_log(event)
            else:
                self.event_unknown.append(event)
            if not len(list(self.event_waiting[event_name].keys())):
                self.event_waiting.pop(event_name, None)
                self.event_filters.pop(event_name, None)

    def wait(self, seconds: int) -> None:
        try:
            with Timeout(seconds) as timeout:
                while len(list(self.event_waiting.keys())):
                    timeout.sleep(2)
        except Exception as e:
            echo(e, err=True)
            message = "NO EVENTS WERE TRIGGERED FOR: " + str(self.event_waiting)
            if len(self.event_unknown) > 0:
                message += "\n UNKOWN EVENTS: " + str(self.event_unknown)

            # FIXME Events triggered in an internal transaction
            # don't have the transactionHash we are looking for here
            # so we just check if the number of unknown events we find
            # is the same as the found events
            waiting_events = sum([len(lst) for lst in self.event_waiting.values()])

            if waiting_events == len(self.event_unknown):
                sandwitch_echo(message)
            else:
                raise Exception(
                    message + " waiting_events " + str(waiting_events),
                    " len(self.event_unknown) " + str(len(self.event_unknown)),
                )

    def assert_event(
        self, txn_hash: str, event_name: str, args: List[Any], timeout: int = 5
    ) -> None:
        """Assert that `event_name` is emitted with the `args`

        For use in tests only.
        """

        def assert_args(event: Dict[str, Any]) -> None:
            assert event["args"] == args, f'{event["args"]} == {args}'

        self.add(txn_hash=txn_hash, event_name=event_name, callback=assert_args)
        self.check(timeout=timeout)


def sandwitch_echo(msg: str) -> None:
    echo("----------------------------------", err=True)
    echo(msg, err=True)
    echo("----------------------------------", err=True)


class LogFilter:
    def __init__(
        self,
        web3: Web3,
        abi: ABI,
        address: ChecksumAddress,
        event_name: str,
        from_block: BlockNumber = GenesisBlock,
        to_block: BlockIdentifier = "latest",
        filters: Any = None,
        callback: Optional[Callable[..., Any]] = None,
    ):
        self.web3 = web3
        self.event_name = event_name

        # Callback for every registered log
        self.callback = callback

        event_abi = [i for i in abi if i["type"] == "event" and i["name"] == event_name]
        if len(event_abi) == 0:
            raise ValueError(f"Event of name {event_name} not found")

        self.event_abi = cast(ABIEvent, event_abi[0])
        assert self.event_abi

        filters = filters if filters else {}

        data_filter_set, filter_params = construct_event_filter_params(
            event_abi=self.event_abi,
            abi_codec=web3.codec,
            contract_address=address,
            argument_filters=filters,
            fromBlock=from_block,
            toBlock=to_block,
        )
        log_data_extract_fn = functools.partial(get_event_data, web3.codec, event_abi)

        self.filter: Web3LogFilter = web3.eth.filter(filter_params)
        self.filter.set_data_filters(data_filter_set)  # type: ignore
        self.filter.log_entry_formatter = log_data_extract_fn
        self.filter.filter_params = filter_params

    def init(self, post_callback: Optional[Callable[[], None]] = None) -> None:
        for log in self.get_logs():
            log["event"] = self.event_name
            if self.callback:
                self.callback(log)
        if post_callback:
            post_callback()

    def get_logs(self) -> List[Any]:
        assert self.filter.filter_id is not None
        logs = self.web3.eth.get_filter_logs(self.filter.filter_id)
        formatted_logs = []
        for log in [dict(log) for log in logs]:
            formatted_logs.append(self.set_log_data(log))
        return formatted_logs

    def set_log_data(self, log: Dict[str, Any]) -> Dict[str, Any]:
        log["args"] = get_event_data(
            abi_codec=self.web3.codec, event_abi=self.event_abi, log_entry=log
        )["args"]
        log["event"] = self.event_name
        return log

    def uninstall(self) -> None:
        assert self.web3 is not None
        assert self.filter is not None
        assert self.filter.filter_id is not None
        self.web3.eth.uninstallFilter(self.filter.filter_id)
        del self.filter
