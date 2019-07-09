pragma solidity 0.5.4;

import "lib/ECVerify.sol";
import "raiden/Token.sol";
import "raiden/Utils.sol";
import "raiden/TokenNetwork.sol";
import "services/ServiceRegistry.sol";
import "services/UserDeposit.sol";

contract MonitoringService is Utils {
    // Token to be used for paying the rewards
    Token public token;

    // Raiden Service Bundle contract to use for checking if MS has deposits
    ServiceRegistry public service_registry;
    UserDeposit public user_deposit;

    // keccak256(channel_identifier, token_network_address) => Struct
    // Keep track of the rewards per channel
    mapping(bytes32 => Reward) internal rewards;

    /*
     *  Structs
     */
    struct Reward{
        // The amount of tokens to be rewarded
        uint256 reward_amount;

        // Nonce of the most recently provided BP
        uint256 nonce;

        // Address of the Raiden Node that was monitored
        // This is also the address that has the reward deducted from its deposit
        address reward_sender_address;

        // Address of the Monitoring Service who is currently eligible to claim the reward
        address monitoring_service_address;
    }

    /*
     *  Events
     */

    event NewBalanceProofReceived(
        address token_network_address,
        uint256 channel_identifier,
        uint256 reward_amount,
        uint256 indexed nonce,
        address indexed ms_address,
        address indexed raiden_node_address
    );
    event RewardClaimed(address indexed ms_address, uint amount, bytes32 indexed reward_identifier);

    /*
     *  Constructor
     */

    /// @notice Set the default values for the smart contract
    /// @param _token_address The address of the token to use for rewards
    /// @param _service_registry_address The address of the ServiceRegistry contract
    constructor(
        address _token_address,
        address _service_registry_address,
        address _udc_address
    )
        public
    {
        require(_token_address != address(0x0), "Token at address zero");
        require(_service_registry_address != address(0x0), "ServiceRegistry at address zero");
        require(_udc_address != address(0x0), "UDC at address zero");
        require(contractExists(_token_address), "token has no code");
        require(contractExists(_service_registry_address), "ServiceRegistry has no code");
        require(contractExists(_udc_address), "UDC has no code");

        token = Token(_token_address);
        service_registry = ServiceRegistry(_service_registry_address);
        user_deposit = UserDeposit(_udc_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0, "Token with zero total supply");
        // Check if the contract is indeed a service_registry contract
        // TODO: Check that some function exists in the contract
    }

    /// @notice Internal function that updates the Reward struct if a newer balance proof
    /// is provided in the monitor() function
    /// @param token_network_address Address of the TokenNetwork being monitored
    /// @param closing_participant The address of the participant who closed the channel
    /// @param non_closing_participant Address of the other channel participant. This is
    /// the participant on whose behalf the MS acts.
    /// @param reward_amount The amount of tokens to be rewarded
    /// @param nonce The nonce of the newly provided balance_proof
    /// @param monitoring_service_address The address of the MS calling monitor()
    /// @param non_closing_signature Non-closing participant signature of the
    /// balance proof data.
    /// @param reward_proof_signature The signature of the signed reward proof
    function updateReward(
        address token_network_address,
        address closing_participant,
        address non_closing_participant,
        uint256 reward_amount,
        uint256 nonce,
        address monitoring_service_address,
        bytes memory non_closing_signature,
        bytes memory reward_proof_signature
    )
        internal
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
        uint256 channel_identifier = token_network.getChannelIdentifier(
            closing_participant, non_closing_participant
        );

        // Make sure that the reward proof is signed by the non_closing_participant
        address raiden_node_address = recoverAddressFromRewardProof(
            address(this),
            token_network.chain_id(),
            non_closing_signature,
            reward_amount,
            reward_proof_signature
        );
        require(raiden_node_address == non_closing_participant, "Bad reward proof");

        bytes32 reward_identifier = keccak256(abi.encodePacked(
            channel_identifier,
            token_network_address
        ));

        // Get the Reward struct for the correct channel
        Reward storage reward = rewards[reward_identifier];

        // Only allow BPs with higher nonce to be submitted
        require(reward.nonce < nonce, "stale nonce");

        // MSC stores channel_identifier, MS_address, reward_amount, nonce
        // of the MS that provided the balance_proof with highest nonce
        rewards[reward_identifier] = Reward({
            reward_amount: reward_amount,
            nonce: nonce,
            reward_sender_address: non_closing_participant,
            monitoring_service_address: monitoring_service_address
        });
    }

    /// @notice Called by a registered MS, when providing a new balance proof
    /// to a monitored channel.
    /// Can be called multiple times by different registered MSs as long as the BP provided
    /// is newer than the current newest registered BP.
    /// @param nonce Strictly monotonic value used to order BPs
    /// omitting PB specific params, since these will not be provided in the future
    /// @param reward_amount Amount of tokens to be rewarded
    /// @param token_network_address Address of the Token Network in which the channel
    /// being monitored exists.
    /// @param reward_proof_signature The signature of the signed reward proof
    function monitor(
        address closing_participant,
        address non_closing_participant,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes memory closing_signature,
        bytes memory non_closing_signature,
        uint256 reward_amount,
        address token_network_address,
        bytes memory reward_proof_signature
    )
        public
    {
        // Call updateReward first to avoid reentrancy problems when the
        // token_network_address belongs to a malicious contract.
        updateReward(
            token_network_address,
            closing_participant,
            non_closing_participant,
            reward_amount,
            nonce,
            msg.sender,
            non_closing_signature,
            reward_proof_signature
        );

        TokenNetwork token_network = TokenNetwork(token_network_address);
        uint256 channel_identifier = token_network.getChannelIdentifier(
            closing_participant, non_closing_participant
        );
        require(isAllowedToMonitor(
            token_network, channel_identifier,
            closing_participant, non_closing_participant, msg.sender
        ), "not allowed to monitor");

        // Call updateTransfer in the corresponding TokenNetwork
        token_network.updateNonClosingBalanceProof(
            channel_identifier,
            closing_participant,
            non_closing_participant,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            non_closing_signature
        );

        emit NewBalanceProofReceived(
            token_network_address,
            channel_identifier,
            reward_amount,
            nonce,
            msg.sender,
            non_closing_participant
        );
    }

    function isAllowedToMonitor(
        TokenNetwork token_network,
        uint256 channel_identifier,
        address closing_participant,
        address non_closing_participant,
        address monitoring_service_address
    )
        internal
        returns (bool)
    {
        TokenNetwork.ChannelState channel_state;
        uint256 settle_block_number;
        (settle_block_number, channel_state) = token_network.getChannelInfo(
            channel_identifier, closing_participant, non_closing_participant
        );
        require(channel_state == TokenNetwork.ChannelState.Closed, "channel not closed");

        // We don't actually know when the channel has been closed. So we'll
        // make a guess so that assumed_close_block >= real_close_block.
        uint256 assumed_settle_timeout = token_network.settlement_timeout_min();
        require(settle_block_number >= assumed_settle_timeout, "too low settle block number");
        uint256 assumed_close_block = settle_block_number - assumed_settle_timeout;
        return block.number >= firstBlockAllowedToMonitor(
            assumed_close_block,
            assumed_settle_timeout,
            closing_participant,
            non_closing_participant,
            monitoring_service_address
        );
    }

    function firstBlockAllowedToMonitor(
        uint256 closed_at_block,
        uint256 settle_timeout,
        address participant1,
        address participant2,
        address monitoring_service_address
    )
        public pure
        returns (uint256)
    {
        // avoid overflows when multiplying with percentages
        require(settle_timeout < uint256(2**256 - 1) / 100, "maliciously big settle timeout");
        require(closed_at_block < uint256(2**256 - 1) / 100, "maliciously big closed_at_block");

        // First allowed block as percentage of settle_timeout. We're using
        // integers here to avoid accuracy loss during calculations.
        uint256 BEST_CASE = 30;
        uint256 WORST_CASE = 80;

        // When is the first block that any MS might be allowed to monitor
        uint256 best_case_block = closed_at_block + BEST_CASE * settle_timeout / 100;
        // Length of the range into which the first allowed block will fall
        uint256 range_length = (WORST_CASE - BEST_CASE) * settle_timeout / 100;

        // Offset for this specific MS within the range
        uint256 ms_offset = (
            uint256(participant1)
            + uint256(participant2)
            + uint256(monitoring_service_address)
        ) % range_length;

        return best_case_block + ms_offset;
    }

    /// @notice Called after a monitored channel is settled in order for MS to claim the reward
    /// Can be called once per settled channel by everyone on behalf of MS
    /// @param token_network_address Address of the Token Network in which the channel exists
    /// @param closing_participant Address of the participant of the channel that called close
    /// @param non_closing_participant The other participant of the channel
    function claimReward(
        uint256 channel_identifier,
        address token_network_address,
        address closing_participant,
        address non_closing_participant
    )
        public
        returns (bool)
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
        bytes32 reward_identifier = keccak256(abi.encodePacked(
            channel_identifier,
            token_network_address
        ));

        // Only allowed to claim, if channel is settled
        // Channel is settled if it's data has been deleted
        TokenNetwork.ChannelState channel_state;
        uint256 settle_block_number;
        (settle_block_number, channel_state) = token_network.getChannelInfo(
            channel_identifier,
            closing_participant,
            non_closing_participant
        );
        require(channel_state == TokenNetwork.ChannelState.Closed ||
            channel_state == TokenNetwork.ChannelState.Settled ||
            channel_state == TokenNetwork.ChannelState.Removed, "too early channel state");
        require(settle_block_number < block.number, "channel not settled yet");

        Reward storage reward = rewards[reward_identifier];

        // Make sure that the Reward exists
        require(reward.reward_sender_address != address(0x0), "reward_sender is zero");

        // Add reward to the monitoring service's balance
        require(user_deposit.transfer(
            reward.reward_sender_address,
            reward.monitoring_service_address,
            reward.reward_amount
        ), "UDC did not transfer");

        emit RewardClaimed(
            reward.monitoring_service_address,
            reward.reward_amount,
            reward_identifier
        );

        // delete storage
        delete rewards[reward_identifier];

        return true;
    }

    function recoverAddressFromRewardProof(
        address monitoring_service_contract_address,
        uint256 chain_id,
        bytes memory non_closing_signature,
        uint256 reward_amount,
        bytes memory signature
    )
        internal
        pure
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n181",  // 20 + 32 + 32 + 65 + 32
            monitoring_service_contract_address,
            chain_id,
            uint256(MessageTypeId.MSReward),
            non_closing_signature,
            reward_amount
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
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
