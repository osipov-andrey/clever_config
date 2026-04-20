# clever_config

Stop using external calls (for instance - `boto3`) and `os.getenv()` across your codebase. **Mark your config values once, resolve them all in one call.**

```python
config = {
    "database": {
        "host":     "prod-db.internal",                                        # plain values stay as-is
        "password": {"type": "SSM",  "value": "/myapp/prod/db-password"},
        "api_key":  {"type": "ENV",  "value": "STRIPE_KEY"},
    },
    "encryption_key": {"type": "KMS", "value": "<base64-kms-ciphertext>"},
}

errors = dict_traversal(config, [SSMAction(), EnvLoaderAction(), KMSAction()])

# config["database"]["password"]  → fetched from SSM Parameter Store
# config["database"]["api_key"]   → read from the environment
# config["encryption_key"]        → decrypted by KMS
```

Anchors are resolved **in place** with one function call.

---

## The problem it solves

A typical service ends up with code like this scattered across a dozen files:

```python
db_password = boto3.client("ssm").get_parameter(Name="/prod/db-pass", WithDecryption=True)["Parameter"]["Value"]
api_key = os.environ["STRIPE_KEY"]
secret = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId="myapp/stripe")["SecretString"])
```

This is tedious to write, hard to test, and makes it unclear at a glance what your service actually needs at startup.

`clever_config` flips the model: **declare what each value is and where it lives, then fetch everything at once** — with batching, default fallbacks, and collected errors built in.

---

## Install

```bash
pip install clever_config
# or with Poetry:
poetry add clever_config
```

Requires Python 3.12+. Runtime dependencies: `boto3`, `requests`.

---

## How it works

An **anchor** is a small dict that marks a value to be resolved:

```python
{"type": "SSM", "value": "/my/app/secret"}
```

Scatter anchors anywhere in your config — at any depth, inside nested dicts or lists. Call `dict_traversal()` with the actions that match your anchor types, and each anchor is replaced with its real value in place.

You can also add a `"default"` key as a fallback for when a value is missing:

```python
{"type": "ENV", "value": "DEBUG_MODE", "default": "false"}
```

---

## Available actions

| Action | Anchor `type` | What it fetches |
|---|---|---|
| `EnvLoaderAction` | `ENV` | An environment variable |
| `KMSAction` | `KMS` | KMS-decrypted value (base64 ciphertext → plaintext) |
| `SSMAction` | `SSM` | SSM Parameter Store — full path |
| `PrefixSSMAction` | `APP-SSM` | SSM with an auto-prepended path prefix |
| `ConventionalSSMAction` | `DEFAULT-SSM` | SSM with `/profile/service/name` convention |
| `ConventionalAppSSMAction` | `CNV-SSM` | SSM with `/app/profile/service/name` convention |
| `SecretManagerAction` | `SECRET-MANAGER` | An AWS Secrets Manager secret |
| `SecretManagerKeysAction` | `SECRET-MANAGER-KEY` | A specific key from a JSON secret (`my-secret.key`) |

All imports are available from `clever_config.actions`.

---

## Usage examples

### Mixing multiple sources

```python
from clever_config.dict_traversal import dict_traversal
from clever_config.actions import SSMAction, SecretManagerAction, EnvLoaderAction

config = {
    "app": {
        "debug":       {"type": "ENV",            "value": "APP_DEBUG",          "default": "false"},
        "db_password": {"type": "SSM",            "value": "/myapp/prod/db-pass"},
        "stripe":      {"type": "SECRET-MANAGER", "value": "myapp/stripe"},
    }
}

errors = dict_traversal(config, [SSMAction(), SecretManagerAction(), EnvLoaderAction()])
if errors:
    raise RuntimeError(f"Config errors:\n" + "\n".join(errors))
```

### SSM with a shared path prefix

```python
from clever_config.actions import PrefixSSMAction

# No need to repeat the prefix in every anchor
action = PrefixSSMAction(prefix="myapp/prod")

config = {
    "db_host":     {"type": "APP-SSM", "value": "db-host"},      # resolves to /myapp/prod/db-host
    "db_password": {"type": "APP-SSM", "value": "db-password"},  # resolves to /myapp/prod/db-password
}
errors = dict_traversal(config, [action])
```

### Extracting individual keys from a JSON secret

```python
from clever_config.actions import SecretManagerKeysAction

# The secret "myapp/db-creds" stores: {"user": "admin", "pass": "s3cr3t"}
config = {
    "db_user": {"type": "SECRET-MANAGER-KEY", "value": "myapp/db-creds.user"},
    "db_pass": {"type": "SECRET-MANAGER-KEY", "value": "myapp/db-creds.pass"},
}
errors = dict_traversal(config, [SecretManagerKeysAction()])
```

### Lambda — using the Parameters & Secrets Extension

Skip the boto3 round-trip inside Lambda by using the sidecar HTTP client instead:

```python
from clever_config.actions import SSMAction

action = SSMAction(use_ssm_lambda_extension=True)
```

This uses the [AWS Parameters and Secrets Lambda Extension](https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-integration-lambda-extensions.html) and reads from `localhost` — faster cold starts, no extra IAM calls.

### Deserializing JSON values

If a parameter value is a JSON string, pass `deserialize_values=True` to parse it automatically into a dict or list:

```python
SSMAction(deserialize_values=True)
SecretManagerAction(deserialize_values=True)
```

---

## Key behaviors

**Errors are collected, not thrown.**
`dict_traversal` returns a list of error strings. Each failed lookup is appended to the list, so you see all problems at once rather than failing on the first missing value. Fatal misconfigurations (e.g. two actions with the same type in one call) raise immediately.

**AWS reads are batched.**
SSM and Secrets Manager actions collect all required paths during traversal, then fetch them in chunks of 10 — minimizing the number of AWS round-trips regardless of how many anchors you have.

**Any nesting is supported.**
Anchors inside lists, deeply nested dicts, or mixed structures are all found and resolved.

**Plain values are untouched.**
Only dicts shaped exactly like an anchor (`{"type": "...", "value": "..."}`) are resolved. Everything else passes through unchanged.

---

## Development

```bash
make test           # run unit tests
make coverage       # tests + coverage report
make lint           # mypy type check
make check-format   # formatting check
make build          # build the package
```

---

## Releasing to PyPI

Publishing is automated on tag push via [`.github/workflows/publish-pypi.yml`](.github/workflows/publish-pypi.yml).

1. Bump `version` in `pyproject.toml`, commit, and merge to your default branch.
2. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`
3. Configure **PyPI Trusted Publishing** for this repository ([setup guide](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)) with environment name **`pypi`**.

The workflow builds with `python -m build` (PEP 517 / `poetry-core`). To use an API token instead of OIDC, see the comment at the top of the workflow file.

---

## License

[MIT](LICENSE) · [github.com/osipov-andrey/clever_config](https://github.com/osipov-andrey/clever_config)
