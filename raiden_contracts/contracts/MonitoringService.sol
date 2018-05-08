pragma solidity ^0.4.23;

import "./Token.sol";
import "./Utils.sol";
import "./lib/ECVerify.sol";
import "./TokenNetwork.sol";

contract MonitoringService is Utils {

    // Token to be used for paying the rewards
    Token public token; // Only allow RDN?

    // The minimum allowed deposit for a MS
    uint256 public minimum_deposit;

    // keep track of registered Monitoring Services
    // A Monitoring Services must deposit to register
    mapping(address => bool) public registered_monitoring_services;

    // channel_identifier => Struct
    // Keep track of the rewards per channel
    mapping(bytes32 => Reward) rewards;

    // Keep track of balances
    mapping(address => uint) public balances;

    /*
     *  Structs
     */
    struct Reward{
        // The signature of the reward
        bytes reward_proof_signature;

        // Nonce of the most recently provided BP
        uint256 nonce;

        // Address of the Raiden Node that was monitored
        // This is also the address that has the reward deducted from its deposit
        address reward_sender_address;
    }

    /*
     *  Events
     */

    //event MonitoringServiceNewDeposit(address sender, address receiver, uint amount);
    event NewDeposit(address sender, address receiver, uint amount);
    event RegisteredMonitoringService(address monitoring_service);
    event NewBalanceProofReceived(
        bytes reward_proof_signature,
        uint256 nonce,
        address ms_address,
        address raiden_node_address
    );
    event RewardClaimed(address ms_address, uint amount, bytes32 channel_id);
    event MonitoringServiceRegistered(address ms_address);
    event MonitoringServiceDeregistered(address ms_address);
    event Withdrawn(address account, uint amount);

    /*
     *  Modifiers 
     */

    modifier isMonitor(address _ms_address) {
        require(registered_monitoring_services[_ms_address]);
        _;
    }

    modifier isNotMonitor(address raiden_node_address) {
        require(!registered_monitoring_services[raiden_node_address]);
        _;
    }

    /*
     *  Constructor
     */

    /// @notice Set the default values for the smart contract
    /// @param _token_address The address of the token to use for rewards
    /// @param _minimum_deposit The minimum value that a MS must deposit to be registered
    constructor(
        address _token_address,
        uint256 _minimum_deposit
    )
        public
    {
        require(_token_address != 0x0);
        require(_minimum_deposit > 0);
        require(contractExists(_token_address));

        minimum_deposit = _minimum_deposit;

        token = Token(_token_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
    }

    /// @notice Deposit tokens used to either pay MSs or to regsiter as MS
    /// Can be called by anyone several times and on behalf of other accounts
    /// @param beneficiary The account benefitting from the deposit
    /// @param amount The amount of tokens to be depositted
    function deposit(address beneficiary, uint amount) public {
        require(amount > 0);

        // This also allows for registered MSs to deposit and use other MSs
        balances[beneficiary] += amount;

        // Transfer the deposit to the smart contract
        require(token.transferFrom(msg.sender, address(this), amount));

        emit NewDeposit(msg.sender, beneficiary, amount);
    }

    /// @notice Deposit and register as Monitoring Service in one function call
    /// Can be called once and is only callable by addresses not already registered as MS
    function depositAndRegisterMonitoringService() isNotMonitor(msg.sender) public {
        uint amount_to_deposit = minimum_deposit - balances[msg.sender];

        // Deposit the amount needed to register
        deposit(msg.sender, amount_to_deposit);
        // Register as a Monitoring Service
        require(registerMonitoringService());
    }

	function updateReward(
		address token_network_address,
		address closing_participant,
		address non_closing_participant,
		bytes reward_proof_signature,
		uint256 nonce,
		address reward_sender_address
	)
	internal
	{
        TokenNetwork token_network = TokenNetwork(token_network_address);
		bytes32 channel_identifier = token_network.getChannelIdentifier(closing_participant, non_closing_participant);
        // Get the Reward struct for the correct channel
        Reward storage reward = rewards[channel_identifier];

        // Only allow PBs with higher nonce to be submitted
        require(reward.nonce < nonce);

        // MSC stores channel_identifier, MS_address, reward_amount, nonce
        // of the MS that provided the balance_proof with highest nonce
        rewards[channel_identifier] = Reward({
            reward_proof_signature: reward_proof_signature,
            nonce: nonce,
            reward_sender_address: reward_sender_address
        });
	}

    /// @notice Called by a registered MS, when providing a new balance proof
    /// to a monitored channel.
    /// Can be called multiple times by different registered MSs as long as the PB provided
    /// is newer than the current newest registered BP.
    /// @param nonce Strictly monotonic value used to order BPs
    /// omitting PB specific params, since these will not be provided in the future
    /// @param reward_proof_signature Signature of the Raiden Node signing the reward
    /// @param token_network_address Address of the Token Network in which the channel
    /// being monitored exists.
    function monitor(
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes closing_signature,
        bytes non_closing_signature,
        address reward_sender_address,
        bytes reward_proof_signature,
        address token_network_address,
        address closing_participant,
        address non_closing_participant
    )
        isMonitor(msg.sender)
        public
    {
		updateReward(
			token_network_address,
			closing_participant,
			non_closing_participant,
			reward_proof_signature,
			nonce,
			reward_sender_address
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
            reward_proof_signature,
            nonce,
            msg.sender,
            reward_sender_address
        );
    }

    /// @notice Called after a monitored channel is settled in order for MS to claim the reward
    /// Can be called once per settled channel by everyone on behalf of MS
    /// @param token_network_address Address of the Token Network in which the channel
    /// @param reward_amount Amount to be paid as reward to the MS
    /// @param monitor_address Address of the MS
    function claimReward(
        address token_network_address,
        uint192 reward_amount,
        address monitor_address,
        address closing_participant,
        address non_closing_participant
    )
        public
        returns (bool)
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
		bytes32 channel_identifier = token_network.getChannelIdentifier(closing_participant, non_closing_participant);

        // Only allowed to claim, if channel is settled
        // Channel is settled if it's data has been deleted
        uint256 channel_settle_block;
        (, channel_settle_block, ) = token_network.getChannelInfo(closing_participant, non_closing_participant);
        require(channel_settle_block == 0);

        Reward storage reward = rewards[channel_identifier];

        // Make sure that the Reward exists
        require(reward.reward_sender_address != 0x0);

        address raiden_node_address = recoverAddressFromRewardProof(
            channel_identifier,
            reward_amount,
            token_network_address,
            token_network.chain_id(),
            reward.nonce,
            monitor_address,
            reward.reward_proof_signature
        );

        // Deduct reward from raiden_node deposit
        balances[raiden_node_address] -= reward_amount;
        // Add reward to the monitoring services' balance.
        // This minimizes the amount of gas cost
        // Only use token.transfer in the withdraw function
        balances[monitor_address] += reward_amount;

        emit RewardClaimed(monitor_address, reward_amount, channel_identifier);

        // delete storage
        delete rewards[channel_identifier];
    }

    /// @notice Withdraw depositted tokens. If msg.sender is MS don't allow to
    /// withdraw below minimum_deposit.
    /// Can be called by addresses with a deposit as long as they have a positive balance
    /// @param amount Amount of tokens to be withdrawn
    function withdraw(uint amount) public {
        // TODO: make sure that deposits reserved for open rewards cannot be withdrawn
        if (registered_monitoring_services[msg.sender]) {
            require(balances[msg.sender] - amount >= minimum_deposit);
            balances[msg.sender] -= amount;
            require(token.transfer(msg.sender, amount));
        } else {
            require(balances[msg.sender] - amount >= 0);
            balances[msg.sender] -= amount;
            require(token.transfer(msg.sender, amount));
        }
        emit Withdrawn(msg.sender, amount);
    }

    /// @notice Allow an address with a balance equal to or above minimum_deposit to
    /// register as Monitoring Service.
    function registerMonitoringService() isNotMonitor(msg.sender) public returns (bool) {
        // only allow to register if not already registered
        require(!registered_monitoring_services[msg.sender]);
        if (balances[msg.sender] >= minimum_deposit) {
            registered_monitoring_services[msg.sender] = true;
            emit MonitoringServiceRegistered(msg.sender);
            return true;
        } else {
            return false;
        }
    }

    /// @notice Let Monitoring Services deregister as monitoring services.
    /// Only callable by registered Monitoring Services
    function deregisterMonitoringService() isMonitor(msg.sender) public {
        registered_monitoring_services[msg.sender] = false;
        emit MonitoringServiceDeregistered(msg.sender);
    }

    function recoverAddressFromRewardProof(
        bytes32 channel_identifier,
        uint192 reward_amount,
        address token_network_address,
        uint256 chain_id,
        uint256 nonce,
        address monitor_address,
        bytes signature
    )
        pure
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(
            channel_identifier,
            reward_amount,
            token_network_address,
            chain_id,
            nonce,
            monitor_address
        );

        signature_address = ECVerify.ecverify(message_hash, signature);
    }
}
