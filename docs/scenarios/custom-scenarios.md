# Custom scenarios

Choose a built-in scenario and use JSON to specify facts that must be true in the audit result. See [screen-boot.json](../../scenarios/screen-boot.json) for an example.

```sh
python3 blackwall report --scenario-file scenarios/screen-boot.json --serve
```

`schema` is `1`; `name` is the display name; `base` is `normal` or `unknown-boot-marker`; and `require_facts` is a list of Boolean fact names from the audit result. The report and command fail if a specified fact is missing or not true. This format does not change execution timing or run arbitrary commands. A general-purpose scripting interface for defining other hardware models and execution behavior is not yet provided.

To find available fact names from a previous execution, inspect `facts` in `run/audit/report.json` inside its private output directory. Firmware and model validation always retain the checks of the base scenario.
