pragma solidity 0.5.4;

/// @title Endpoint Registry
/// @notice This contract is a registry which maps an Ethereum address to its
/// endpoint. The Raiden node registers its ethereum address in this registry.
contract EndpointRegistry {
    string constant public contract_version = "0.14.0";

    event AddressRegistered(address indexed eth_address, string endpoint);
    mapping (address => string) private address_to_endpoint;

    modifier noEmptyString(string memory str) {
        require(equals(str, "") != true);
        _;
    }

    /// @notice Registers the Ethereum address to the given endpoint.
    /// @param endpoint String in the format "127.0.0.1:38647".
    function registerEndpoint(string memory endpoint)
        public
        noEmptyString(endpoint)
    {
        string storage old_endpoint = address_to_endpoint[msg.sender];

        // Compare if the new endpoint matches the old one, if it does just
        // return
        if (equals(old_endpoint, endpoint)) {
            return;
        }

        // Update the storage with the new endpoint value
        address_to_endpoint[msg.sender] = endpoint;
        emit AddressRegistered(msg.sender, endpoint);
    }

    /// @notice Finds the endpoint if given a registered Ethereum address.
    /// @param eth_address A 20 byte Ethereum address.
    /// @return endpoint which the current Ethereum address is using.
    function findEndpointByAddress(address eth_address)
        public
        view
        returns (string memory endpoint)
    {
        return address_to_endpoint[eth_address];
    }

    /// @notice Checks if two strings are equal or not.
    /// @param a First string.
    /// @param b Second string.
    /// @return result True if `a` and `b` are equal, false otherwise.
    function equals(string memory a, string memory b) internal pure returns (bool result)
    {
        return (keccak256(abi.encodePacked(a)) == keccak256(abi.encodePacked(b)));
    }
}


// MIT License

// Copyright (c) 2018

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
