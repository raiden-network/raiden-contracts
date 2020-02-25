import json
import pprint
import time
from typing import Dict

import click
import requests
from eth_abi import encode_abi
from web3 import HTTPProvider, Web3
from web3.middleware import geth_poa_middleware

from raiden_contracts.constants import DeploymentModule
from raiden_contracts.contract_manager import contracts_precompiled_path
from raiden_contracts.deploy.__main__ import validate_address
from raiden_contracts.deploy.etherscan_verify import (
    USER_AGENT,
    api_of_chain_id,
    guid_status,
    join_sources,
)
from raiden_contracts.utils.type_aliases import ChainID

CONTRACT_TO_MODULE = {
    "CustomToken": DeploymentModule.TOKENS,
}


@click.command()
@click.option(
    "--rpc-provider", default="http://127.0.0.1:8545", help="Address of the Ethereum RPC provider"
)
@click.option("--apikey", required=True, help="A valid Etherscan APIKEY is required.")
@click.option(
    "--address", callback=validate_address,
)
@click.option("--args",)
def etherscan_verify(apikey: str, rpc_provider: str, address: str, args: str) -> None:
    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={"timeout": 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print("Web3 provider is", web3.providers[0])

    code = bytes(web3.eth.getCode(address))
    print(code[:30].hex())

    with open(contracts_precompiled_path()) as f:
        contracts = json.load(f)["contracts"]
    for name, con in contracts.items():
        if not con["bin-runtime"]:
            continue
        con_code = bytes.fromhex(con["bin-runtime"])
        if code[:-100] == con_code[:-100]:
            print("Deployed code matches " + name)
            for func in con["abi"]:
                if func["type"] == "constructor":

                    if not args:
                        print("Use `--args` to pass all constructor arguments (comma separated):")
                        for var in func["inputs"]:
                            print("\t", var["name"], var["type"])
                        exit()

                    # Constructor arguments
                    types = [arg["type"] for arg in func["inputs"]]
                    args_list = [
                        (int(a) if t.startswith("uint") else a)
                        for a, t in zip(args.split(","), types)
                    ]
                    print(args_list)
                    assert len(args_list) == len(types), "Incorrect number of args"
                    encoded_args = encode_abi(types, args_list)
                    print(encoded_args.hex())

                    verify_this(
                        chain_id=ChainID(int(web3.net.version)),
                        apikey=apikey,
                        address=address,
                        contract_name=name,
                        metadata=json.loads(con["metadata"]),
                        constructor_args=encoded_args.hex(),
                    )
                    break


def verify_this(
    chain_id: ChainID,
    apikey: str,
    address: str,
    # source: str,
    contract_name: str,
    metadata: Dict,
    constructor_args: str,
) -> None:
    source = (
        join_sources(source_module=CONTRACT_TO_MODULE[contract_name], contract_name=contract_name),
    )
    data = {
        # A valid API-Key is required
        "apikey": apikey,
        # Do not change
        "module": "contract",
        # Do not change
        "action": "verifysourcecode",
        "contractaddress": address,
        "sourceCode": source,
        "contractname": contract_name,
        "compilerversion": "v" + metadata["compiler"]["version"],
        # 0 = Optimization used, 1 = No Optimization
        "optimizationUsed": 0 if metadata["settings"]["optimizer"]["enabled"] is False else 1,
        "runs": metadata["settings"]["optimizer"]["runs"],
        # Typo is intentional. Etherscan does not like the correct spelling.
        "constructorArguements": constructor_args,
    }
    pprint.pprint({k: v for k, v in data.items() if k != "sourceCode"})
    return

    etherscan_api = api_of_chain_id[chain_id]
    response = requests.post(etherscan_api, data=data, headers={"User-Agent": USER_AGENT})
    try:
        content = response.json()
    except json.decoder.JSONDecodeError:
        print(response.text)
        raise
    print(content)
    print(f'Status: {content["status"]}; {content["message"]} ; GUID = {content["result"]}')

    etherscan_url = etherscan_api.replace("api-", "").replace("api", "")
    etherscan_url += "/verifyContract2?a=" + data["contractaddress"]
    manual_submission_guide = f"""Usually a manual submission to Etherscan works.
    Visit {etherscan_url}
    Use raiden_contracts/deploy/joined.sol."""

    if content["status"] != "1":
        if content["result"] == "Contract source code already verified":
            return
        else:
            raise ValueError(
                "Etherscan submission failed for an unknown reason\n" + manual_submission_guide
            )

    # submission succeeded, obtained GUID
    guid = content["result"]
    status = "0"
    retries = 10
    while status == "0" and retries > 0:
        retries -= 1
        r = guid_status(etherscan_api=etherscan_api, guid=guid)
        status = r["status"]
        if r["result"] == "Fail - Unable to verify":
            raise ValueError(manual_submission_guide)
        if r["result"] == "Pass - Verified":
            return
        print("Retrying...")
        time.sleep(5)
    raise TimeoutError(manual_submission_guide)


if __name__ == "__main__":
    # pylint: disable=E1120
    etherscan_verify()
