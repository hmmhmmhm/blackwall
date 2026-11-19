# Scenarios

This directory contains a custom scenario example. `screen-boot.json` adds checks for the original boot path and display buffer to the built-in `normal` execution.

```sh
python3 blackwall report --scenario-file scenarios/screen-boot.json --serve
```

See the [scenario guide](../docs/scenarios/README.md) for the built-in scenarios and how to write your own.
