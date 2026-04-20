import abc
from dataclasses import dataclass, fields
from typing import Any, List, Union


class ActionException(Exception):
    pass


@dataclass
class ActionAnchor:
    type: str
    value: str


@dataclass
class AnchorWithDefault(ActionAnchor):
    type: str
    value: str
    default: Any = None


def get_anchor(obj: Any) -> ActionAnchor | AnchorWithDefault | None:
    if isinstance(obj, dict):
        if isinstance(obj, dict):
            if list(obj.keys()) == [field.name for field in fields(AnchorWithDefault)]:
                return AnchorWithDefault(**obj)
            if list(obj.keys()) == [field.name for field in fields(ActionAnchor)]:
                return ActionAnchor(**obj)
    return None


# None is valid value to return, so we need to mark somehow when there's no value to return at all
class MissedValue:
    ...


class BaseAction(abc.ABC):
    action_type: str

    def get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> Any:
        """
        Get value from the anchor according to action logic if anchor type equals to action_type
        :param path_chain: value path in config
        :param anchor: ActionAnchor
        :return: value from the anchor according to action logic or None
        """
        if self._is_needed(anchor):
            try:
                value = self._get_value(path_chain, anchor)
            except ActionException:
                if isinstance(anchor, AnchorWithDefault):
                    return anchor.default
                raise
            return value
        return MissedValue()

    @staticmethod
    def path_to_str(path_chain: List[Union[str, int]]) -> str:
        return " -> ".join(str(el) for el in path_chain)

    def _is_needed(self, anchor: ActionAnchor) -> bool:
        return anchor.type.lower().strip() == self.action_type.lower().strip()

    @abc.abstractmethod
    def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> Any:
        """Get value from the anchor according to action logic"""
        pass

    def __pre_traversal_hook__(self, mapping: dict) -> List[str]:
        return []

    def __post_traversal_hook__(self, mapping: dict) -> List[str]:
        return []
