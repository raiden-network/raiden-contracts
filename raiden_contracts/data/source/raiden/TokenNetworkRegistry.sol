// SPDX-License-Identifier: MIT
/* solium-disable error-reason */
pragma solidity 0.8.10;
pragma abicoder v2;

import "raiden/Utils.sol";
import "raiden/Token.sol";
import "raiden/TokenNetwork.sol";
import "raiden/Controllable.sol";

/// @title TokenNetworkRegistry
/// @notice The TokenNetwork Registry deploys new TokenNetwork contracts for the
/// Raiden Network protocol.
contract TokenNetworkRegistry is Utils, Controllable {
    address public secret_registry_address;
    uint256 public settle_timeout;
    uint256 public max_token_networks;

    // Only for the limited Red Eyes release
    uint256 public token_network_created = 0;

    // Token address => TokenNetwork address
    mapping(address => address) public token_to_token_networks;

    event TokenNetworkCreated(address indexed token_address, address indexed token_network_address, uint256 settle_timeout);

    modifier canCreateTokenNetwork() {
        require(token_network_created < max_token_networks, "TNR: registry full");
        _;
    }

    /// @param _secret_registry_address The address of SecretRegistry that's used by all
    /// TokenNetworks created by this contract
    /// that can be chosen at the channel opening
    /// @param _settle_timeout Number of seconds that need to elapse between a
    /// call to closeChannel and settleChannel
    /// @param _max_token_networks the number of tokens that can be registered
    /// MAX_UINT256 means no limits
    constructor(
        address _secret_registry_address,
        uint256 _settle_timeout,
        uint256 _max_token_networks
    ) {
        require(_secret_registry_address != address(0x0), "TNR: invalid SR address");
        require(contractExists(_secret_registry_address), "TNR: invalid SR");
        require(_max_token_networks > 0, "TNR: invalid TN limit");
        require(_settle_timeout > 0, "TNR: invalid settle timeout");
        secret_registry_address = _secret_registry_address;

        settle_timeout = _settle_timeout;

        max_token_networks = _max_token_networks;

        controller = msg.sender;
    }

    /// @notice Deploy a new TokenNetwork contract for the Token deployed at
    /// `_token_address`
    /// @param _token_address Ethereum address of an already deployed token, to
    /// be used in the new TokenNetwork contract
    function createERC20TokenNetwork(
        address _token_address,
        uint256 _channel_participant_deposit_limit,
        uint256 _token_network_deposit_limit
    )
        public
        canCreateTokenNetwork
        returns (address token_network_address)
    {
        // After the limits have been removed, new token networks must be created without limits
        // See https://github.com/raiden-network/raiden-contracts/issues/1416
        if (max_token_networks == MAX_SAFE_UINT256) {
            require(_channel_participant_deposit_limit == MAX_SAFE_UINT256, "TNR: limits must be set to MAX_INT");
            require(_token_network_deposit_limit == MAX_SAFE_UINT256, "TNR: limits must be set to MAX_INT");
        }

        require(token_to_token_networks[_token_address] == address(0x0), "TNR: token already registered");

        // We limit the number of token networks to 1 for the Bug Bounty release
        token_network_created = token_network_created + 1;

        TokenNetwork token_network;

        // Token contract checks are in the corresponding TokenNetwork contract
        token_network = new TokenNetwork(
            _token_address,
            secret_registry_address,
            settle_timeout,
            controller,
            _channel_participant_deposit_limit,
            _token_network_deposit_limit
        );

        token_network_address = address(token_network);

        token_to_token_networks[_token_address] = token_network_address;
        emit TokenNetworkCreated(_token_address, token_network_address, settle_timeout);

        return token_network_address;
    }

    function createERC20TokenNetworkWithoutLimits(
        address _token_address
    )
        external
        returns (address token_network_address)
    {
        return createERC20TokenNetwork(_token_address, MAX_SAFE_UINT256, MAX_SAFE_UINT256);
    }

    /// @notice Removes the limit on the number of token networks.
    /// Can only be called by the controller.
    function removeLimits()
        external
        onlyController
    {
        max_token_networks = MAX_SAFE_UINT256;
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
