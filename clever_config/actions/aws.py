import abc
import base64
import json
import logging
import os
from abc import ABC
from json import JSONDecodeError
from typing import Any, Dict, Generator, List, Optional, Set, Union

import boto3
import requests
from boto3.exceptions import Boto3Error
from botocore.exceptions import BotoCoreError, ClientError

from clever_config.actions.base import ActionAnchor, ActionException, BaseAction
from clever_config.utils import (
    IncompatiblePathAndMappingException,
    change_value_in_mapping,
)

KeyOrIndex = Union[str, int]


class AwsActionError(Exception):
    pass


class KMSAction(BaseAction):
    """
    Takes decrypted value from KMS.

    How to encrypt with AWS CLI:
    aws kms encrypt \
        --key-id 1234abcd-12ab-34cd-56ef-1234567890ab \
        --plaintext fileb://ExamplePlaintextFile \
        --output text \
        --query CiphertextBlob

    See more: https://docs.aws.amazon.com/cli/latest/reference/kms/encrypt.html
    """

    action_type = "KMS"

    def __init__(self, key_id: Optional[str] = None) -> None:
        super().__init__()
        self.key_id = key_id

    def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
        encrypted_value: bytes = base64.b64decode(anchor.value.encode())
        decrypt_kwargs: Dict[str, Union[str, bytes]] = dict(CiphertextBlob=encrypted_value)
        if self.key_id:
            decrypt_kwargs["KeyId"] = self.key_id
        try:
            decrypted_value: bytes = boto3.client("kms").decrypt(**decrypt_kwargs)["Plaintext"]
        except (Boto3Error, BotoCoreError, ClientError) as err:
            path_in_config: str = " -> ".join(str(elem) for elem in path_chain)
            raise ActionException(
                f'KMS cipher on this path "{path_in_config}" cannot be decrypted! '
                f"Error: {err.__class__.__name__}: {str(err)}"
            )
        value = decrypted_value.decode().strip()
        return value


class BaseBatchAction(BaseAction, abc.ABC):
    REQUEST_CHUNK = 10
    encrypt_log: bool = False

    def __init__(self, deserialize_values: bool = False):
        self.deserialize_values = deserialize_values
        self._config_parameters_storage: List[BaseSSMAction.ConfigParameter] = list()

    class ConfigParameter:
        def __init__(self, config_path: list, parameter_name: str):
            self.config_path = config_path
            self.parameter_name = parameter_name

        def __repr__(self) -> str:
            return f'<{"/".join(self.config_path)}>'

    def save_config_parameter(self, name: str, path: list) -> None:
        self._config_parameters_storage.append(BaseSSMAction.ConfigParameter(config_path=path, parameter_name=name))

    def _get_parameters(self, parameter_paths: List[str]) -> dict:
        raise NotImplementedError()

    def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
        """Collect all SSM parameters to get them all in one request later"""
        parameter_name: str = self._get_parameter_full_name(anchor.value)
        self.save_config_parameter(parameter_name, path_chain)
        return "PLACEHOLDER, will be gotten by batch request."

    def _get_parameter_names(self) -> Generator[List[str], None, None]:
        # sorted for convenience mocks for testing
        parameter_names = list(sorted({parameter.parameter_name for parameter in self._config_parameters_storage}))
        for i in range(0, len(parameter_names), self.REQUEST_CHUNK):
            yield parameter_names[i : i + self.REQUEST_CHUNK]  # noqa: E203

    def deserialize_value(self, parameter: str, path: List[KeyOrIndex]) -> Union[str, int, list, dict]:
        if not self.deserialize_values:
            return parameter
        transformed_value = parameter
        try:
            transformed_value = json.loads(str(parameter))
            logging.debug(f"value {self.path_to_str(path)} is converted to json.")
        except Exception:
            logging.debug(f"value {self.path_to_str(path)} can't be converted to json, skipped")
        return transformed_value

    def __post_traversal_hook__(self, mapping: dict) -> List[str]:
        if not self._config_parameters_storage:
            return []
        errors: List[str] = []
        founded_parameters = dict()
        for param_names_chunk in self._get_parameter_names():
            try:
                parameters_info = self._get_parameters(param_names_chunk)
            except AwsActionError as error:
                errors.append(
                    f"Could not get {self.action_type} parameters: {', '.join(param_names_chunk)}. Error: {error}"
                )
                continue
            founded_parameters.update(parameters_info)

        diff = self._check_all_requested_values(set(founded_parameters.keys()))
        if diff:
            errors.append(f"The following parameters are missing in {self.action_type}: {diff}")

        for config_parameter in self._config_parameters_storage:
            if config_parameter.parameter_name not in founded_parameters:
                continue
            value = self.deserialize_value(
                founded_parameters[config_parameter.parameter_name], config_parameter.config_path
            )
            try:
                change_value_in_mapping(mapping, value, config_parameter.config_path)
            except IncompatiblePathAndMappingException as err:
                errors.append(str(err))

        return errors

    def _check_all_requested_values(self, actual_values: set) -> Set[str]:
        requested_values = set(parameter.parameter_name for parameter in self._config_parameters_storage)
        diff = requested_values - actual_values
        return diff

    @abc.abstractmethod
    def _get_parameter_full_name(self, parameter_name: str) -> str:
        pass


class BaseSSMAction(BaseBatchAction, ABC):
    """
    Takes parameter's value from SSM.

    First of all, it saves the names of all the necessary parameters and the paths to them in the config.
    Further, it takes all the values from SSM in one request and places them in the config.
    """

    def __init__(self, use_ssm_lambda_extension: bool = False, deserialize_values: bool = False) -> None:
        super().__init__(deserialize_values)
        self.use_ssm_lambda_extension = use_ssm_lambda_extension

    def _get_parameters(self, parameter_paths: List[str]) -> dict:
        parameters_info = (
            self._get_ssm_extension_parameters(parameter_paths)
            if self.use_ssm_lambda_extension
            else self._get_boto3_ssm_parameters(parameter_paths)
        )
        return {parameter["Name"]: parameter["Value"] for parameter in parameters_info["Parameters"]}

    def _get_boto3_ssm_parameters(self, parameter_paths: List[str]) -> dict:
        ssm_client = boto3.client("ssm")
        try:
            return ssm_client.get_parameters(Names=parameter_paths, WithDecryption=True)
        except BotoCoreError as error:
            raise AwsActionError(f"Could not get SSM Parameters {parameter_paths} not found. Error: {error}")

    def _get_ssm_extension_parameters(self, parameter_paths: List[str]):
        parameters: Dict[str, list] = {"Parameters": []}
        for parameter_path in parameter_paths:
            parameters["Parameters"].append(self._make_lambda_ssm_extension_request(parameter_path))
        return parameters

    def _make_lambda_ssm_extension_request(self, parameter_path: str) -> dict:
        # Documentation: https://docs.aws.amazon.com/
        # systems-manager/latest/userguide/ps-integration-lambda-extensions.html#ps-integration-lambda-extensions-add

        ssm_lambda_extension_port = os.environ.get("PARAMETERS_SECRETS_EXTENSION_HTTP_PORT", default="2773")

        response = requests.get(
            url=(
                f"http://localhost:{ssm_lambda_extension_port}/"
                f"systemsmanager/parameters/get?name={parameter_path}&withDecryption=true"
            ),
            headers={"X-Aws-Parameters-Secrets-Token": os.environ["AWS_SESSION_TOKEN"]},
        )

        if response.status_code != 200:
            error_msg = (
                "Invalid response from lambda ssm extension. "
                f"StatusCode: {response.status_code}. Response: {response.text}"
            )
            raise AwsActionError(error_msg)

        try:
            response_json = response.json()
        except JSONDecodeError:
            error_msg = f"Invalid response from lambda ssm extension. Response is not JSON: {response.text}"
            raise AwsActionError(error_msg)

        if response_json["Parameter"]["Name"] != parameter_path:
            error_msg = (
                "Invalid parameter founded. "
                f"Requested parameter path: {parameter_path}"
                f"Response parameter path: {response_json['Parameter']['Name']}"
            )
            raise AwsActionError(error_msg)

        return response_json["Parameter"]


class SSMAction(BaseSSMAction):
    """
    Takes parameter's value from SSM.

    First of all, it saves the names of all the necessary parameters and the paths to them in the config.
    Further, it takes all the values from SSM in one request and places them in the config.
    """

    action_type = "SSM"

    def _get_parameter_full_name(self, parameter_name: str) -> str:
        return parameter_name


class ConventionalSSMAction(BaseSSMAction):
    """
    SSM Action with parameter name calculation for default parameters:
    https://git.ringcentral.com/groups/cds/-/wikis/configuration_management
    """

    action_type = "DEFAULT-SSM"

    def __init__(
        self, profile: str, service_name: str, use_ssm_lambda_extension: bool = False, deserialize_values: bool = False
    ):
        super().__init__(use_ssm_lambda_extension=use_ssm_lambda_extension, deserialize_values=deserialize_values)
        self.profile = profile
        self.service_name = service_name

    def _get_parameter_full_name(self, parameter_name: str) -> str:
        return f"/{self.profile}/{self.service_name}/{parameter_name}"


class ConventionalAppSSMAction(BaseSSMAction):
    """
    SSM Action with parameter name calculation for Application specific parameters:
    https://git.ringcentral.com/groups/cds/-/wikis/configuration_management
    """

    action_type = "CNV-SSM"

    def __init__(
        self,
        application: str,
        profile: str,
        service_name: str,
        use_ssm_lambda_extension: bool = False,
        deserialize_values: bool = False,
    ):
        super().__init__(use_ssm_lambda_extension=use_ssm_lambda_extension, deserialize_values=deserialize_values)
        self.application = application
        self.profile = profile
        self.service_name = service_name

    def _get_parameter_full_name(self, parameter_name: str) -> str:
        return f"/{self.application}/{self.profile}/{self.service_name}/{parameter_name}"


class PrefixSSMAction(BaseSSMAction):
    action_type = "APP-SSM"

    def __init__(self, prefix: str, use_ssm_lambda_extension: bool = False, deserialize_values: bool = False):
        super().__init__(use_ssm_lambda_extension=use_ssm_lambda_extension, deserialize_values=deserialize_values)
        self.prefix = prefix.strip("/")

    def _get_parameter_full_name(self, parameter_name: str) -> str:
        return f"/{self.prefix}/{parameter_name}"


class SecretManagerAction(BaseBatchAction):
    """
    Takes value from AWS Secret Manager.
    """

    action_type = "SECRET-MANAGER"
    encrypt_log = True

    def __init__(self, deserialize_values: bool = False, prefix: str = ""):
        super().__init__(deserialize_values)
        self.prefix = ("/" + prefix.strip("/") + "/") if prefix else ""

    def _get_parameters(self, parameter_paths: List[str]) -> dict:
        secret_mananager_client = boto3.client("secretsmanager")
        try:
            parameters_info = secret_mananager_client.batch_get_secret_value(SecretIdList=parameter_paths)
        except BotoCoreError as error:
            raise AwsActionError(f"Could not get Secret Parameters {parameter_paths} not found. Error: {error}")
        return {parameter["Name"]: parameter["SecretString"] for parameter in parameters_info["SecretValues"]}

    def _get_parameter_full_name(self, parameter_name: str) -> str:
        return f"{self.prefix}{parameter_name}"


class SecretManagerKeysAction(SecretManagerAction):
    """
    The Action that also extracts nested keys from AWS SecretManager secrets.
    usage:
        field_with_secret:
            type: SECRET-MANAGER-KEY
            value: <secret-name>.<secret-key>
        the_whole_secret:
            type: SECRET-MANAGER-KEY
            value: <secret-name>
    """

    action_type = "SECRET-MANAGER-KEY"

    def _get_parameters(self, parameter_paths: list[str]) -> dict:
        """
        Process parameter paths to extract values from AWS Secrets Manager.

        Supports two formats:
        - 'secret-name.key' - extracts specific JSON key from secret
        - 'secret-name' - returns entire secret value
        """
        # Parse parameter paths into structured data
        secret_requests = self._parse_parameter_paths(parameter_paths)

        # Fetch all unique secrets from AWS
        secret_names = list(secret_requests.keys())
        raw_secrets = super()._get_parameters(secret_names)

        # Process each request and extract the required values
        result = {}
        errors = []

        for parameter_path in parameter_paths:
            try:
                secret_name, secret_key = self._parse_single_parameter_path(parameter_path)

                if secret_name not in raw_secrets:
                    continue  # Will be handled by missing parameter check in parent class

                secret_value = raw_secrets[secret_name]
                extracted_value = self._extract_value_from_secret(secret_value, secret_key, parameter_path)

                # Maintain backward compatibility with the original key format
                result_key = self._generate_result_key(secret_name, secret_key)
                result[result_key] = extracted_value

            except (json.JSONDecodeError, KeyError) as err:
                errors.append(
                    f"Could not process parameter '{parameter_path}'. " f"Error: {err.__class__.__name__}({err})"
                )

        if errors:
            raise AwsActionError("\n".join(errors))

        return result

    def _parse_parameter_paths(self, parameter_paths: list[str]) -> dict:
        """Parse parameter paths and group by secret name."""
        secret_requests: dict[str, list[str]] = {}
        for parameter_path in parameter_paths:
            secret_name, secret_key = self._parse_single_parameter_path(parameter_path)
            if secret_name not in secret_requests:
                secret_requests[secret_name] = []
            if secret_key:
                secret_requests[secret_name].append(secret_key)
        return secret_requests

    @staticmethod
    def _parse_single_parameter_path(parameter_path: str) -> tuple[str, str | None]:
        """Parse a single parameter path into secret name and optional key."""
        try:
            secret_name, secret_key = parameter_path.split(".", maxsplit=1)
            return secret_name, secret_key
        except ValueError:
            return parameter_path, None

    @staticmethod
    def _extract_value_from_secret(secret_value: str, secret_key: str | None, parameter_path: str) -> Any:
        """Extract the requested value from a secret."""
        if secret_key is None:
            # Return entire secret value
            return secret_value

        # Extract specific key from JSON secret
        try:
            secret_json = json.loads(secret_value)
            return secret_json[secret_key]
        except json.JSONDecodeError as err:
            raise json.JSONDecodeError(
                f"Secret contains invalid JSON for parameter '{parameter_path}'", err.doc, err.pos
            ) from err
        except KeyError as err:
            raise KeyError(f"Key '{secret_key}' not found in secret for parameter '{parameter_path}'") from err

    @staticmethod
    def _generate_result_key(secret_name: str, secret_key: str | None) -> str:
        """Generate result key maintaining backward compatibility with original format."""
        if secret_key is None:
            # For whole secrets, append dot (original behavior)
            return f"{secret_name}."
        else:
            # For key extraction, use secret_name.key format
            return f"{secret_name}.{secret_key}"
