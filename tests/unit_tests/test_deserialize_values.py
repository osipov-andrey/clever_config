import unittest
from typing import List, Union

from clever_config.actions import ActionAnchor
from clever_config.actions.aws import BaseSSMAction
from clever_config.dict_traversal import dict_traversal


class TestDictTraversalDeserialize(unittest.TestCase):
    class TestAction(BaseSSMAction):
        action_type = "test"

        def _get_boto3_ssm_parameters(self, parameter_paths: List[str]) -> dict:
            return {
                "Parameters": [
                    {
                        "Name": "full_path_prefix/value1",
                        "Value": '{"abacaba": {"bar": {"type": "test", "value": "value2"}}}',
                    },
                    {
                        "Name": "full_path_prefix/value2",
                        "Value": '{"lol": "kek"}',
                    },
                    {
                        "Name": "full_path_prefix/value3",
                        "Value": "{not valid json}",
                    },
                ]
            }

        def _get_parameter_full_name(self, parameter_name: str) -> str:
            return f"full_path_prefix/{parameter_name}"

        def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
            parameter_name: str = self._get_parameter_full_name(anchor.value)
            self.save_config_parameter(parameter_name, path_chain)
            return "SSM_PLACEHOLDER. Should be replaced by value from SSM!"

    def test_dict_traversal(self):
        test_input = {"baz": {"foo": {"type": "test", "value": "value1"}}}
        expected_output = {"baz": {"foo": {"abacaba": {"bar": {"lol": "kek"}}}}}

        dict_traversal(test_input, [TestDictTraversalDeserialize.TestAction(deserialize_values=True)])
        dict_traversal(test_input, [TestDictTraversalDeserialize.TestAction(deserialize_values=True)])

        self.assertEqual(expected_output, test_input)

    def test_dict_traversal_cannot_convert(self):
        test_input = {"foo": {"type": "test", "value": "value3"}}
        expected_output = {"foo": "{not valid json}"}

        dict_traversal(test_input, [TestDictTraversalDeserialize.TestAction(deserialize_values=True)])

        self.assertEqual(expected_output, test_input)
