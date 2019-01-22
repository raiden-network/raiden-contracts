# Raiden Smart Contracts Development Guide

## Code Style

### Solidity

For solidity we generally follow the style guide as shown in the [solidity
documentation](http://solidity.readthedocs.io/en/develop/style-guide.html) with
some exceptions:

**Variable Names**

All variable name should be in snake case, just like in python. Function names
on the other hand should be mixedCase. MixedCase is essentially like CamelCase
but with the initial letter being a small letter. This helps us to easily
determine which function calls are smart contract calls in the python code
side.

```js
function iDoSomething(uint awesome_argument) {
    doSomethingElse();
}
```

### Python

This repository follows the same guidelines as the Raiden Client, regarding the Python code used in tests and scripts: https://github.com/raiden-network/raiden/blob/master/CONTRIBUTING.md#coding-style.
