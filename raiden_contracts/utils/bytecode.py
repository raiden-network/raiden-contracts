def runtime_hexcode(contracts_manager, name):
    """ Calculate the runtime hexcode from the deployment bytecode

    Parameters:
        name: name of the contract such as CONTRACT_TOKEN_NETWORK
    """
    compiled_bytecode = contracts_manager.contracts[name]['bin-runtime']
    compiled_bytecode = hex(int(compiled_bytecode, 16))
    return compiled_bytecode
