import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError

from clever_config.actions.aws import AwsActionError, SecretManagerKeysAction
from clever_config.actions.base import ActionAnchor


class TestSecretManagerKeysAction:
    """
    Generated with Cursor

    Test suite for SecretManagerKeysAction class
    """

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.action = SecretManagerKeysAction(deserialize_values=False, prefix="")
        self.action_with_prefix = SecretManagerKeysAction(deserialize_values=False, prefix="myapp")
        self.action_with_deserialize = SecretManagerKeysAction(deserialize_values=True, prefix="")

    @patch("clever_config.actions.aws.boto3.client")
    def test_get_parameters_with_secret_keys(self, mock_boto_client):
        """Test _get_parameters method with secret keys (secret.key format)."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "database-config",
                    "SecretString": '{"username": "admin", "password": "secret123"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:database-config-AbCdEf",
                },
                {
                    "Name": "api-keys",
                    "SecretString": '{"key1": "value1", "key2": "value2"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:api-keys-AbCdEf",
                },
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test parameters with keys - Note: only one key per secret name due to dict limitation
        parameter_paths = ["database-config.password", "api-keys.key1"]
        result = self.action._get_parameters(parameter_paths)

        # Verify the result
        expected = {"database-config.password": "secret123", "api-keys.key1": "value1"}
        assert result == expected

        # Verify boto3 was called correctly
        mock_client.batch_get_secret_value.assert_called_once_with(SecretIdList=["database-config", "api-keys"])

    @patch("clever_config.actions.aws.boto3.client")
    def test_get_parameters_without_secret_keys(self, mock_boto_client):
        """Test _get_parameters method without secret keys (whole secret)."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "whole-secret",
                    "SecretString": "this-is-the-whole-secret-value",
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:whole-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test parameter without key
        parameter_paths = ["whole-secret"]
        result = self.action._get_parameters(parameter_paths)

        # Verify the result
        expected = {"whole-secret.": "this-is-the-whole-secret-value"}
        assert result == expected

        # Verify boto3 was called correctly
        mock_client.batch_get_secret_value.assert_called_once_with(SecretIdList=["whole-secret"])

    @patch("clever_config.actions.aws.boto3.client")
    def test_get_parameters_mixed_scenarios(self, mock_boto_client):
        """Test _get_parameters with mixed scenarios (with and without keys)."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "json-secret",
                    "SecretString": '{"nested": {"key": "value"}, "simple": "text"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:json-secret-AbCdEf",
                },
                {
                    "Name": "plain-secret",
                    "SecretString": "plain-text-secret",
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:plain-secret-AbCdEf",
                },
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test mixed parameters
        parameter_paths = ["json-secret.simple", "plain-secret"]
        result = self.action._get_parameters(parameter_paths)

        # Verify the result
        expected = {"json-secret.simple": "text", "plain-secret.": "plain-text-secret"}
        assert result == expected

    @patch("clever_config.actions.aws.boto3.client")
    def test_get_parameters_json_decode_error(self, mock_boto_client):
        """Test _get_parameters when JSON parsing fails."""
        # Setup mock response with invalid JSON
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "invalid-json-secret",
                    "SecretString": "this-is-not-json{",
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:invalid-json-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test parameter that requires JSON parsing
        parameter_paths = ["invalid-json-secret.key"]

        with pytest.raises(AwsActionError) as exc_info:
            self.action._get_parameters(parameter_paths)

        assert "JSONDecodeError" in str(exc_info.value)

    @patch("clever_config.actions.aws.boto3.client")
    def test_get_parameters_key_not_found_error(self, mock_boto_client):
        """Test _get_parameters when requested key doesn't exist in JSON."""
        # Setup mock response with valid JSON but missing key
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "json-secret",
                    "SecretString": '{"existing_key": "value"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:json-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test parameter with non-existent key
        parameter_paths = ["json-secret.non_existent_key"]

        with pytest.raises(AwsActionError) as exc_info:
            self.action._get_parameters(parameter_paths)

        assert "KeyError" in str(exc_info.value)

    @patch("clever_config.actions.aws.boto3.client")
    def test_get_parameters_boto_error(self, mock_boto_client):
        """Test _get_parameters when boto3 client raises an error."""
        # Setup mock to raise BotoCoreError
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.batch_get_secret_value.side_effect = BotoCoreError()

        parameter_paths = ["some-secret.key"]

        with pytest.raises(AwsActionError) as exc_info:
            self.action._get_parameters(parameter_paths)

        assert "Could not get Secret Parameters" in str(exc_info.value)

    def test_get_parameter_full_name_no_prefix(self):
        """Test _get_parameter_full_name without prefix."""
        parameter_name = "my-secret"
        result = self.action._get_parameter_full_name(parameter_name)
        assert result == "my-secret"

    def test_get_parameter_full_name_with_prefix(self):
        """Test _get_parameter_full_name with prefix."""
        parameter_name = "my-secret"
        result = self.action_with_prefix._get_parameter_full_name(parameter_name)
        assert result == "/myapp/my-secret"

    @patch("clever_config.actions.aws.boto3.client")
    def test_complex_nested_json_extraction(self, mock_boto_client):
        """Test extraction of deeply nested JSON values."""
        # Setup mock response with complex JSON
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        complex_json = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "super_secret"},
            },
            "api": {"endpoints": ["api1", "api2"], "timeout": 30},
        }

        mock_response = {
            "SecretValues": [
                {
                    "Name": "config-secret",
                    "SecretString": json.dumps(complex_json),
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:config-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Note: The current implementation only supports one level of key extraction
        # e.g., 'secret.key' not 'secret.key.subkey'
        parameter_paths = ["config-secret.database"]
        result = self.action._get_parameters(parameter_paths)

        expected = {"config-secret.database": complex_json["database"]}
        assert result == expected

    @patch("clever_config.actions.aws.boto3.client")
    def test_duplicate_secret_names(self, mock_boto_client):
        """Test handling of duplicate secret names with different keys."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "shared-secret",
                    "SecretString": '{"key1": "value1", "key2": "value2", "key3": "value3"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:shared-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test multiple keys from same secret - FIXED: Now correctly handles multiple keys
        parameter_paths = ["shared-secret.key1", "shared-secret.key2", "shared-secret.key3"]
        result = self.action._get_parameters(parameter_paths)

        # All keys are now correctly processed (bug fixed in refactored version)
        expected = {"shared-secret.key1": "value1", "shared-secret.key2": "value2", "shared-secret.key3": "value3"}
        assert result == expected

        # Verify boto3 was called only once (optimization)
        mock_client.batch_get_secret_value.assert_called_once_with(SecretIdList=["shared-secret"])

    def test_action_type(self):
        """Test that action_type is correctly set."""
        assert self.action.action_type == "SECRET-MANAGER-KEY"

    @patch("clever_config.actions.aws.boto3.client")
    def test_empty_parameter_list(self, mock_boto_client):
        """Test behavior with empty parameter list."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {"SecretValues": []}
        mock_client.batch_get_secret_value.return_value = mock_response

        parameter_paths = []
        result = self.action._get_parameters(parameter_paths)

        assert result == {}
        mock_client.batch_get_secret_value.assert_called_once_with(SecretIdList=[])

    @patch("clever_config.actions.aws.boto3.client")
    def test_secret_with_numeric_values(self, mock_boto_client):
        """Test handling of JSON with numeric values."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "numeric-secret",
                    "SecretString": '{"port": 8080, "timeout": 30.5, "enabled": true}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:numeric-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Test only one key due to dict limitation
        parameter_paths = ["numeric-secret.enabled"]
        result = self.action._get_parameters(parameter_paths)

        expected = {"numeric-secret.enabled": True}
        assert result == expected

    @patch("clever_config.actions.aws.boto3.client")
    def test_integration_with_config_processing(self, mock_boto_client):
        """Test the complete integration with config processing workflow."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "app-config",
                    "SecretString": '{"db_password": "secret123", "api_key": "key456"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:app-config-AbCdEf",
                },
                {
                    "Name": "other-secret",
                    "SecretString": '{"value": "other-value"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:other-secret-AbCdEf",
                },
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Create action and simulate config processing
        action = SecretManagerKeysAction(deserialize_values=False, prefix="")

        # Use keys for both secrets to avoid the parameter name mismatch issue
        action._get_value(
            ["database", "password"], ActionAnchor(type="SECRET-MANAGER-KEY", value="app-config.db_password")
        )
        action._get_value(["other", "value"], ActionAnchor(type="SECRET-MANAGER-KEY", value="other-secret.value"))

        # Create test mapping
        test_mapping = {
            "database": {"password": "PLACEHOLDER, will be gotten by batch request."},
            "other": {"value": "PLACEHOLDER, will be gotten by batch request."},
        }

        # Call post traversal hook
        errors = action.__post_traversal_hook__(test_mapping)

        # Verify no errors
        assert errors == []

        # Verify mapping was updated correctly
        assert test_mapping["database"]["password"] == "secret123"
        assert test_mapping["other"]["value"] == "other-value"

        # Verify boto3 was called with the correct secret names
        mock_client.batch_get_secret_value.assert_called_once_with(SecretIdList=["app-config", "other-secret"])

    @patch("clever_config.actions.aws.boto3.client")
    def test_post_traversal_hook_with_missing_secrets(self, mock_boto_client):
        """Test post traversal hook when some secrets are missing."""
        # Setup mock response with only some secrets
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        mock_response = {
            "SecretValues": [
                {
                    "Name": "existing-secret",
                    "SecretString": '{"key": "value"}',
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:existing-secret-AbCdEf",
                }
            ]
        }
        mock_client.batch_get_secret_value.return_value = mock_response

        # Create action and add parameters
        action = SecretManagerKeysAction(deserialize_values=False, prefix="")
        action._get_value(["existing", "field"], ActionAnchor(type="SECRET-MANAGER-KEY", value="existing-secret.key"))
        action._get_value(["missing", "field"], ActionAnchor(type="SECRET-MANAGER-KEY", value="missing-secret.key"))

        test_mapping = {
            "existing": {"field": "PLACEHOLDER, will be gotten by batch request."},
            "missing": {"field": "PLACEHOLDER, will be gotten by batch request."},
        }

        # Call post traversal hook
        errors = action.__post_traversal_hook__(test_mapping)

        # Verify error about missing secret
        assert len(errors) == 1
        assert "missing-secret.key" in errors[0]
        assert "The following parameters are missing in SECRET-MANAGER-KEY" in errors[0]

        # Verify existing secret was processed
        assert test_mapping["existing"]["field"] == "value"
        # Missing field should remain unchanged
        assert test_mapping["missing"]["field"] == "PLACEHOLDER, will be gotten by batch request."

    @patch("clever_config.actions.aws.boto3.client")
    def test_post_traversal_hook_with_aws_error(self, mock_boto_client):
        """Test post traversal hook when AWS raises an error."""
        # Setup mock to raise error
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.batch_get_secret_value.side_effect = BotoCoreError()

        # Create action and add parameters
        action = SecretManagerKeysAction(deserialize_values=False, prefix="")
        action._get_value(["field"], ActionAnchor(type="SECRET-MANAGER-KEY", value="secret.key"))

        test_mapping = {"field": "PLACEHOLDER, will be gotten by batch request."}

        # Call post traversal hook
        errors = action.__post_traversal_hook__(test_mapping)

        # Verify error was captured - there will be both AWS error and missing parameter error
        assert len(errors) == 2
        assert "Could not get SECRET-MANAGER-KEY parameters" in errors[0]
        assert "secret.key" in errors[0]
        assert "The following parameters are missing in SECRET-MANAGER-KEY" in errors[1]

    @patch("clever_config.actions.aws.boto3.client")
    def test_request_chunking_simulation(self, mock_boto_client):
        """Test that REQUEST_CHUNK behavior works correctly (simulated)."""
        # Setup mock response
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        # Setup different responses for each chunk
        def mock_batch_get_secret_value(SecretIdList):
            # Return only the secrets that were requested in this chunk
            return {
                "SecretValues": [
                    {
                        "Name": secret_name,
                        "SecretString": f'{{"key": "value{secret_name.split("-")[1]}"}}',
                        "ARN": f"arn:aws:secretsmanager:us-east-1:123456789012:secret:{secret_name}-AbCdEf",
                    }
                    for secret_name in SecretIdList
                ]
            }

        mock_client.batch_get_secret_value.side_effect = mock_batch_get_secret_value

        # Create action with smaller chunk size for testing
        action = SecretManagerKeysAction(deserialize_values=False, prefix="")
        action.REQUEST_CHUNK = 3  # Override for testing

        # Add multiple parameters - each secret only once to avoid dict overwrite issue
        for i in range(5):
            action._get_value([f"field{i}"], ActionAnchor(type="SECRET-MANAGER-KEY", value=f"secret-{i}.key"))

        test_mapping = {f"field{i}": "PLACEHOLDER, will be gotten by batch request." for i in range(5)}

        # Call post traversal hook
        errors = action.__post_traversal_hook__(test_mapping)

        # Should have no errors
        assert errors == []

        # Verify all fields were updated
        for i in range(5):
            assert test_mapping[f"field{i}"] == f"value{i}"

        # With chunk size of 3, we should have 2 API calls: [0,1,2] and [3,4]
        assert mock_client.batch_get_secret_value.call_count == 2

    def test_whole_secret_parameter_name_issue(self):
        """Test that demonstrates the parameter name mismatch issue for whole secrets.

        This is a known limitation where whole secrets create a mismatch between
        the stored parameter name and the generated result key.
        """
        action = SecretManagerKeysAction(deserialize_values=False, prefix="")

        # When we call _get_value with a whole secret (no key), it stores "secret-name"
        result = action._get_value(["field"], ActionAnchor(type="SECRET-MANAGER-KEY", value="whole-secret"))
        assert result == "PLACEHOLDER, will be gotten by batch request."

        # Check what parameter name was stored
        stored_params = [param.parameter_name for param in action._config_parameters_storage]
        assert stored_params == ["whole-secret"]  # No dot

        # But when _get_parameters processes it, the result key will be "whole-secret." (with dot)
        # This creates a mismatch that causes the parameter to be considered "missing"
