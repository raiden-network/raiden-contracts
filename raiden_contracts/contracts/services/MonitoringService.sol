pragma solidity ^0.4.23;

import "raiden/Token.sol";
import "raiden/Utils.sol";
import "raiden/lib/ECVerify.sol";
import "raiden/TokenNetwork.sol";
import "raiden/RaidenServiceBundle.sol";

contract MonitoringService is Utils {
    string constant public contract_version = "0.4.0";

    // Token to be used for paying the rewards
    Token public token;

    // Raiden Service Bundle contract to use for checking if MS has deposits
    RaidenServiceBundle public rsb;

    // keccak256(channel_identifier, token_network_address) => Struct
    // Keep track of the rewards per channel
    mapping(bytes32 => Reward) rewards;

    // Keep track of balances
    mapping(address => uint256) public balances;

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

        // Address of the Monitoring Service who is currenly eligible to claim the reward
        address monitoring_service_address;
    }

    /*
     *  Events
     */

    event NewDeposit(address indexed receiver, uint amount);
    event NewBalanceProofReceived(
        uint256 reward_amount,
        uint256 indexed nonce,
        address indexed ms_address,
        address indexed raiden_node_address
    );
    event RewardClaimed(address indexed ms_address, uint amount, bytes32 indexed reward_identifier);
    event Withdrawn(address indexed account, uint amount);

    /*
     *  Modifiers
     */

    modifier canMonitor(address _ms_address) {
        require(rsb.deposits(_ms_address) > 0);
        _;
    }

    /*
     *  Constructor
     */

    /// @notice Set the default values for the smart contract
    /// @param _token_address The address of the token to use for rewards
    /// @param _rsb_address The address of the RaidenServiceBundle contract
    constructor(
        address _token_address,
        address _rsb_address
    )
        public
    {
        require(_token_address != 0x0);
        require(_rsb_address != 0x0);
        require(contractExists(_token_address));
        require(contractExists(_rsb_address));

        token = Token(_token_address);
        rsb = RaidenServiceBundle(_rsb_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
        // Check if the contract is indeed an rsb contract
        // TODO: Check that some function exists in the contract
    }

    /// @notice Deposit tokens used to reward MSs. Idempotent function that sets the
    /// total_deposit of tokens of the beneficiary
    /// Can be called by anyone several times and on behalf of other accounts
    /// @param beneficiary The account benefiting from the deposit
    /// @param total_deposit The sum of tokens, that have been deposited
    function deposit(address beneficiary, uint256 total_deposit) public
    {
        require(total_deposit > balances[beneficiary]);

        uint256 added_deposit;

        // Calculate the actual amount of tokens that will be transferred
        added_deposit = total_deposit - balances[beneficiary];

        // This also allows for MSs to deposit and use other MSs
        balances[beneficiary] += added_deposit;

        emit NewDeposit(beneficiary, added_deposit);

        // Transfer the deposit to the smart contract
        require(token.transferFrom(msg.sender, address(this), added_deposit));

    }

    /// @notice Internal function that updates the Reward struct if a newer balance proof
    /// is provided in the monitor() function
    /// @param token_network_address Address of the TokenNetwork being monitored
    /// @param closing_participant The address of the participant who closed the channel
    /// @param non_closing_participant Address of the other channel participant. This is
    /// the participant on which behalf the MS acts.
    /// @param reward_amount The amount of tokens to be rewarded
    /// @param nonce The nonce of the newly provided balance_proof
    /// @param monitoring_service_address The address of the MS calling monitor()
    /// @param reward_proof_signature The signature of the signed reward proof
    function updateReward(
        address token_network_address,
        address closing_participant,
        address non_closing_participant,
        uint256 reward_amount,
        uint256 nonce,
        address monitoring_service_address,
        bytes reward_proof_signature
    )
    internal
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
        uint256 channel_identifier = token_network.getChannelIdentifier(closing_participant, non_closing_participant);

        // Make sure that the reward proof is signed by the non_closing_participant
        address raiden_node_address = recoverAddressFromRewardProof(
            channel_identifier,
            reward_amount,
            token_network_address,
            token_network.chain_id(),
            nonce,
            reward_proof_signature
        );
        require(raiden_node_address == non_closing_participant);

        bytes32 reward_identifier = keccak256(abi.encodePacked(
            channel_identifier,
            token_network_address
        ));

        // Get the Reward struct for the correct channel
        Reward storage reward = rewards[reward_identifier];

        // Only allow BPs with higher nonce to be submitted
        require(reward.nonce < nonce);

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
    /// Can be called multiple times by different registered MSs as long as the PB provided
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
        bytes closing_signature,
        bytes non_closing_signature,
        uint256 reward_amount,
        address token_network_address,
        bytes reward_proof_signature
    )
        canMonitor(msg.sender)
        public
    {
        updateReward(
            token_network_address,
            closing_participant,
            non_closing_participant,
            reward_amount,
            nonce,
            msg.sender,
            reward_proof_signature
        );
        TokenNetwork token_network = TokenNetwork(token_network_address);

        // Call updateTransfer in the corresponding TokenNetwork
        token_network.updateNonClosingBalanceProof(
            closing_participant,
            non_closing_participant,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            non_closing_signature
        );

        emit NewBalanceProofReceived(
            reward_amount,
            nonce,
            msg.sender,
            non_closing_participant
        );
    }

    /// @notice Called after a monitored channel is settled in order for MS to claim the reward
    /// Can be called once per settled channel by everyone on behalf of MS
    /// @param token_network_address Address of the Token Network in which the channel
    /// @param closing_participant Address of the participant of the channel that called close
    /// @param non_closing_participant The other participant of the channel
    function claimReward(
        address token_network_address,
        address closing_participant,
        address non_closing_participant
    )
        public
        returns (bool)
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
        uint256 channel_identifier = token_network.getChannelIdentifier(
            closing_participant,
            non_closing_participant
        );
        bytes32 reward_identifier = keccak256(abi.encodePacked(
            channel_identifier,
            token_network_address
        ));

        // Only allowed to claim, if channel is settled
        // Channel is settled if it's data has been deleted
        uint8 channel_state;
        (, , channel_state) = token_network.getChannelInfo(
            closing_participant,
            non_closing_participant
        );
        // If channel.state is zero it means it's either non-existing or settled
        require(channel_state == 0);

        Reward storage reward = rewards[reward_identifier];

        // Make sure that the Reward exists
        require(reward.reward_sender_address != 0x0);

        // Deduct reward from raiden_node deposit
        balances[reward.reward_sender_address] -= reward.reward_amount;
        // Add reward to the monitoring services' balance.
        // This minimizes the amount of gas cost
        // Only use token.transfer in the withdraw function
        balances[reward.monitoring_service_address] += reward.reward_amount;

        emit RewardClaimed(
            reward.monitoring_service_address,
            reward.reward_amount,
            reward_identifier
        );

        // delete storage
        delete rewards[reward_identifier];
    }

    /// @notice Withdraw deposited tokens.
    /// Can be called by addresses with a deposit as long as they have a positive balance
    /// @param amount Amount of tokens to be withdrawn
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;
        require(token.transfer(msg.sender, amount));
        emit Withdrawn(msg.sender, amount);
    }

    function recoverAddressFromRewardProof(
        uint256 channel_identifier,
        uint256 reward_amount,
        address token_network_address,
        uint256 chain_id,
        uint256 nonce,
        bytes signature
    )
        pure
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            channel_identifier,
            reward_amount,
            token_network_address,
            chain_id,
            nonce
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }
}
