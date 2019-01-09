def runtime_hexcode(contracts_manager, name, length):
    """ Calculate the runtime hexcode from the deployment bytecode

    Parameters:
        name: name of the contract such as CONTRACT_TOKEN_NETWORK
        length: the length of the runtime code
    """
    compiled_bytecode = contracts_manager.contracts[name]['bin']
    compiled_bytecode = compiled_bytecode[-length:]
    compiled_bytecode = hex(int(compiled_bytecode, 16))
    return compiled_bytecode
