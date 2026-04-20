from typing import List, Union

import pytest

from clever_config.actions.base import (
    ActionAnchor,
    ActionException,
    AnchorWithDefault,
    BaseAction,
    get_anchor,
)


class TestAnchorWithDefault:
    """
    Generated with Cursor

    Test suite for AnchorWithDefault functionality
    """

    def test_get_anchor_creates_anchor_with_default(self):
        """Test that get_anchor properly creates AnchorWithDefault when default is present"""
        anchor_dict = {"type": "test", "value": "test_value", "default": "default_value"}

        result = get_anchor(anchor_dict)

        assert isinstance(result, AnchorWithDefault)
        assert result.type == "test"
        assert result.value == "test_value"
        assert result.default == "default_value"

    def test_get_anchor_creates_regular_anchor_without_default(self):
        """Test that get_anchor creates regular ActionAnchor when no default is present"""
        anchor_dict = {"type": "test", "value": "test_value"}

        result = get_anchor(anchor_dict)

        assert isinstance(result, ActionAnchor)
        assert not isinstance(result, AnchorWithDefault)
        assert result.type == "test"
        assert result.value == "test_value"

    def test_get_anchor_returns_none_for_invalid_dict(self):
        """Test that get_anchor returns None for invalid dictionaries"""
        invalid_dicts = [
            {"type": "test"},  # missing value
            {"value": "test"},  # missing type
            {"type": "test", "value": "test", "extra": "field"},  # extra fields
            {"type": "test", "value": "test", "default": "default", "extra": "field"},  # extra fields
        ]

        for invalid_dict in invalid_dicts:
            result = get_anchor(invalid_dict)
            assert result is None

    def test_anchor_with_default_returns_default_on_action_exception(self):
        """Test that AnchorWithDefault returns default value when ActionException is raised"""

        class FailingAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                raise ActionException("Simulated failure")

        action = FailingAction()
        anchor = AnchorWithDefault(type="test", value="test_value", default="fallback_value")
        path = ["config", "key"]

        result = action.get_value(path, anchor)

        assert result == "fallback_value"

    def test_regular_anchor_reraises_action_exception(self):
        """Test that regular ActionAnchor re-raises ActionException without default"""

        class FailingAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                raise ActionException("Simulated failure")

        action = FailingAction()
        anchor = ActionAnchor(type="test", value="test_value")
        path = ["config", "key"]

        with pytest.raises(ActionException, match="Simulated failure"):
            action.get_value(path, anchor)

    def test_anchor_with_default_returns_normal_value_when_no_exception(self):
        """Test that AnchorWithDefault returns normal value when no exception occurs (default ignored)"""

        class SuccessfulAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                return "successful_value"

        action = SuccessfulAction()
        anchor = AnchorWithDefault(type="test", value="test_value", default="should_be_ignored")
        path = ["config", "key"]

        result = action.get_value(path, anchor)

        assert result == "successful_value"

    def test_regular_anchor_returns_normal_value_when_no_exception(self):
        """Test that regular ActionAnchor returns normal value when no exception occurs"""

        class SuccessfulAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                return "successful_value"

        action = SuccessfulAction()
        anchor = ActionAnchor(type="test", value="test_value")
        path = ["config", "key"]

        result = action.get_value(path, anchor)

        assert result == "successful_value"

    def test_anchor_with_default_none_value(self):
        """Test that None can be used as a valid default value"""

        class FailingAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                raise ActionException("Simulated failure")

        action = FailingAction()
        anchor = AnchorWithDefault(type="test", value="test_value", default=None)
        path = ["config", "key"]

        result = action.get_value(path, anchor)

        assert result is None

    def test_anchor_with_default_complex_value(self):
        """Test that complex objects can be used as default values"""

        class FailingAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                raise ActionException("Simulated failure")

        action = FailingAction()
        default_value = {"key": "value", "list": [1, 2, 3]}
        anchor = AnchorWithDefault(type="test", value="test_value", default=default_value)
        path = ["config", "key"]

        result = action.get_value(path, anchor)

        assert result == default_value

    def test_wrong_action_type_returns_missed_value(self):
        """Test that wrong action type returns MissedValue regardless of anchor type"""

        class TestAction(BaseAction):
            action_type = "different_type"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                return "should_not_be_called"

        action = TestAction()

        # Test with regular anchor
        anchor = ActionAnchor(type="test", value="test_value")
        result = action.get_value(["path"], anchor)
        assert result.__class__.__name__ == "MissedValue"

        # Test with anchor with default
        anchor_with_default = AnchorWithDefault(type="test", value="test_value", default="default")
        result = action.get_value(["path"], anchor_with_default)
        assert result.__class__.__name__ == "MissedValue"

    @pytest.mark.parametrize("default_value", ["string_default", 42, [1, 2, 3], {"key": "value"}, None, True, False])
    def test_anchor_with_default_various_types(self, default_value):
        """Test that various types can be used as default values"""

        class FailingAction(BaseAction):
            action_type = "test"

            def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
                raise ActionException("Simulated failure")

        action = FailingAction()
        anchor = AnchorWithDefault(type="test", value="test_value", default=default_value)
        path = ["config", "key"]

        result = action.get_value(path, anchor)

        assert result == default_value
