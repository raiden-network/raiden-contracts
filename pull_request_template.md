### What this PR does

### Why I'm making this PR

### What's tricky about this PR (if any)

----

Any reviewer can check these:

* [ ] If the PR is fixing a bug or adding a feature, add an entry to CHANGELOG.md.
* [ ] If the PR changed a Solidity source, run `make compile_contracts` and add the resulting `raiden_contracts/data/contracts.json` in the PR.
* [ ] If the PR is changing documentation only, add `[skip ci]` in the commit message so Travis does not waste time.
    * [ ] But, if the PR changes comments in a Solidity source, do not add `[skip ci]` and let Travis check the hash of the source.
* [ ] In Python, use keyword arguments
* [ ] Squash unnecessary commits
* [ ] Comment commits
* [ ] Follow naming conventions
    * `solidityFunction`
    * `_solidity_argument`
    * `solidity_variable`
    * `python_variable`
    * `PYTHON_CONSTANT`
* [ ] Follow the Signature Convention in [CONTRIBUTING.md](./CONTRIBUTING.md)
* For each new contract
    * [ ] The deployment script deploys the new contract.
    * [ ] `etherscan_verify.py` runs on the new contract.
* Bookkeep
    * [ ] The gas cost of new functions are stored in `gas.json`.
* Solidity specific conventions
    * [ ] Document arguments of functions in natspec
    * [ ] Care reentrancy problems
    * if the PR adds or removes `require()` or `assert()`
        * [ ] add an entry in Changelog
        * [ ] open an issue in the client, light client, service repos so the change is reflected there
        * Just adding a message in `require()` doesn't require these steps.
* [ ] When you catch a require() failure in Solidity, look for a specific error message like `pytest.raises(TransactionFailed, match="error message"):`

And before "merge" all checkboxes have to be checked.  If you find redundant points, remove them.