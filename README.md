# clever_config

Walk nested **dict/list** configuration trees and **resolve typed anchors in place** — one traversal, pluggable resolvers for **AWS KMS**, **SSM Parameter Store**, **Secrets Manager**, and **environment variables**. Built for services that keep structure in code or YAML but want secrets and parameters injected at runtime without bespoke glue.

## Features

- **Depth-first traversal** over arbitrary nesting; anchors are plain dicts shaped like `{"type": "<ACTION>", "value": "<payload>"}` (optional `default` for [`AnchorWithDefault`](clever_config/actions/base.py)).
- **Composable actions** — pass a list of actions; each `action_type` must be unique for a single run.
- **Batch AWS reads** — SSM and Secrets Manager actions collect paths first, then fetch in chunks to cut round-trips.
- **Lambda-friendly SSM** — optional HTTP client for the [Parameters and Secrets Lambda extension](https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-integration-lambda-extensions.html).
- **Python 3.12+**, typed-oriented layout (`pyproject.toml` / Poetry).

## Install

```bash
poetry add clever_config
# or, from a checkout:
poetry install
```

Runtime deps: `boto3`, `requests` (see [`pyproject.toml`](pyproject.toml)).

## Usage

```python
from clever_config.dict_traversal import dict_traversal
from clever_config.actions import KMSAction, EnvLoaderAction

config = {
    "app": {
        "api_key": {"type": "ENV", "value": "MY_API_KEY"},
        "token": {"type": "KMS", "value": "<base64-encoded KMS ciphertext>"},
    },
}

errors = dict_traversal(config, [KMSAction(), EnvLoaderAction()])
# `config` is mutated: anchors become resolved strings (or structured values if an action deserializes JSON).
# Non-fatal issues are collected in `errors`; overlapping action types in one call raise.
```

**Actions** (import from `clever_config.actions`): `KMSAction`, `SSMAction`, `PrefixSSMAction`, `ConventionalSSMAction`, `ConventionalAppSSMAction`, `SecretManagerAction`, `SecretManagerKeysAction`, `EnvLoaderAction`. See docstrings in [`clever_config/actions/aws.py`](clever_config/actions/aws.py) and [`clever_config/actions/env.py`](clever_config/actions/env.py) for AWS CLI hints and parameter naming.

## Development

```bash
make test        # unit tests
make coverage    # tests + coverage
make lint        # mypy
make check-format
make build       # poetry build
```

## License

[MIT](LICENSE)

Repository: [github.com/osipov-andrey/python_smart_config](https://github.com/osipov-andrey/python_smart_config)
