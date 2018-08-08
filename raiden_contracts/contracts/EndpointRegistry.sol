pragma solidity ^0.4.23;

/// @title Endpoint Registry
/// @notice This contract is a registry which maps an Ethereum address to its
/// endpoint i.e. sockets. The Ethereum address registers its address in this registry.
contract EndpointRegistry {
    string constant public contract_version = "0.3._";

    event AddressRegistered(address indexed eth_address, string socket);

    // Mapping of Ethereum addresses => SocketEndpoints
    mapping (address => string) address_to_socket;
    // Mapping of SocketEndpoints => Ethereum addresses
    mapping (string => address) socket_to_address;

    modifier noEmptyString(string str) {
        require(equals(str, "") != true);
        _;
    }

    /// @notice Registers the Ethereum address to the Endpoint socket.
    /// @dev Registers the Ethereum address to the Endpoint socket.
    /// @param socket String in the format "127.0.0.1:38647".
    function registerEndpoint(string socket)
        public
        noEmptyString(socket)
    {
        string storage old_socket = address_to_socket[msg.sender];

        // Compare if the new socket matches the old one, if it does just return
        if (equals(old_socket, socket)) {
            return;
        }

        // Set the value for the `old_socket` mapping key to `0`
        socket_to_address[old_socket] = address(0);

        // Update the storage with the new socket value
        address_to_socket[msg.sender] = socket;
        socket_to_address[socket] = msg.sender;
        emit AddressRegistered(msg.sender, socket);
    }

    /// @notice Finds the socket if given a registered Ethereum address.
    /// @dev Finds the socket if given a registered Ethereum address.
    /// @param eth_address A 20 byte Ethereum address.
    /// @return socket which the current Ethereum address is using.
    function findEndpointByAddress(address eth_address) public view returns (string socket)
    {
        return address_to_socket[eth_address];
    }

    /// @notice Finds an Ethereum address if given a registered socket address.
    /// @dev Finds an Ethereum address if given a registered socket address.
    /// @param socket A string in the format "127.0.0.1:38647".
    /// @return eth_address An Ethereum address.
    function findAddressByEndpoint(string socket) public view returns (address eth_address)
    {
        return socket_to_address[socket];
    }

    /// @dev Checks if two strings are equal or not.
    /// @param a First string.
    /// @param b Second string.
    /// @return result True if `a` and `b` are equal, false otherwise.
    function equals(string a, string b) internal pure returns (bool result)
    {
        if (keccak256(abi.encodePacked(a)) == keccak256(abi.encodePacked(b))) {
            return true;
        }

        return false;
    }
}
