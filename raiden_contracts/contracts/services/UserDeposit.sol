pragma solidity ^0.5.2;

import "raiden/Token.sol";
import "raiden/Utils.sol";

contract UserDeposit is Utils {
    string constant public contract_version = "0.4.1";
    uint constant public withdraw_delay = 100;  // time before withdraw is allowed in blocks

    // Token to be used for the deposit
    Token public token;

    // Keep track of balances
    mapping(address => uint256) public balances;
    mapping(address => WithdrawPlan) public withdraw_plans;

    /*
     *  Structs
     */
    struct WithdrawPlan {
        uint256 amount;
        uint256 withdraw_block;  // earliest block at which withdraw is allowed
    }

    /*
     *  Events
     */

    event BalanceReduced(address indexed owner, uint newBalance);
    event WithdrawPlanned(address indexed withdrawer, uint plannedBalance);

    /*
     *  Modifiers
     */

    modifier canTransfer() {
        // TODO: allow only access from MSC and 1-n payment contract
        require(true);
        _;
    }

    /*
     *  Constructor
     */

    /// @notice Set the default values for the smart contract
    /// @param _token_address The address of the token to use for rewards
    constructor(
        address _token_address
    )
        public
    {
        require(_token_address != address(0x0));
        require(contractExists(_token_address));

        token = Token(_token_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
    }

    /// @notice Deposit tokens. Idempotent function that sets the
    /// total_deposit of tokens of the beneficiary.
    /// Can be called by anyone several times and on behalf of other accounts
    /// @param beneficiary The account benefiting from the deposit
    /// @param total_deposit The sum of tokens, that have been deposited
    function deposit(address beneficiary, uint256 total_deposit) public
    {
        require(total_deposit > balances[beneficiary]);

        // Calculate the actual amount of tokens that will be transferred
        uint256 added_deposit = total_deposit - balances[beneficiary];

        balances[beneficiary] += added_deposit;
        require(token.transferFrom(msg.sender, address(this), added_deposit));
    }

    /// @notice Internally transfer deposits between two addresses
    /// The amount will be deducted from the msg sender's balance
    /// @param receiver Account to which the amount will be credited
    /// @param amount Amount of tokens to be withdrawn
    function transfer(
        address sender,
        address receiver,
        uint256 amount
    )
        canTransfer()
        public returns (bool success)
    {
        if (balances[sender] >= amount && amount > 0) {
            balances[sender] -= amount;
            balances[receiver] += amount;
            emit BalanceReduced(sender, balances[sender]);
            return true;
        } else {
            return false;
        }
    }

    /// @notice Announce intention to withdraw tokens.
    /// Sets the planned withdraw amount and resets the withdraw_block
    /// @param amount Maximum amount of tokens to be withdrawn
    function planWithdraw(uint256 amount) public {
        require(amount > 0);
        require(balances[msg.sender] >= amount);

        withdraw_plans[msg.sender] = WithdrawPlan({
            amount: amount,
            withdraw_block: block.number + withdraw_delay
        });
        emit WithdrawPlanned(msg.sender, balances[msg.sender] - amount);
    }

    /// @notice Execute a planned withdrawal
    /// Will only work after the withdraw_delay has expired.
    /// An amount lower or equal to the planned amount may be withdrawn.
    /// Removes the withdraw plan even if not the full amount has been
    /// withdrawn.
    /// @param amount Amount of tokens to be withdrawn
    function withdraw(uint256 amount) public {
        WithdrawPlan storage withdraw_plan = withdraw_plans[msg.sender];
        require(amount <= withdraw_plan.amount);
        require(withdraw_plan.withdraw_block <= block.number);
        //amount = min(amount, balances[msg.sender]);
        amount = amount < balances[msg.sender] ? amount : balances[msg.sender];
        balances[msg.sender] -= amount;
        require(token.transfer(msg.sender, amount));

        emit BalanceReduced(msg.sender, balances[msg.sender]);
        delete withdraw_plans[msg.sender];
    }

    /// @notice The owner's balance with planned withdrawals deducted
    /// @param owner Address for which the balance should be returned
    function effectiveBalance(
        address owner
    )
        public returns (uint256 remaining_balance)
    {
        WithdrawPlan storage withdraw_plan = withdraw_plans[owner];
        return balances[owner] - withdraw_plan.amount;
    }
}
