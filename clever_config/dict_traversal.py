from typing import Any, Callable

from clever_config.actions.base import (
    ActionAnchor,
    ActionException,
    AnchorWithDefault,
    BaseAction,
    MissedValue,
    get_anchor,
)
from clever_config.utils import change_value_in_mapping

JSONTypes = dict | list | str | int
PathList = list[str | int]
CheckedCollection = dict | list
AnchorGetter = Callable[[Any], ActionAnchor | AnchorWithDefault | None]


def dict_traversal(mapping: dict, actions: list[BaseAction], anchor_getter: AnchorGetter = get_anchor) -> list[str]:
    errors = []

    for action in actions:
        errors.extend(action.__pre_traversal_hook__(mapping))

    queue: list[tuple[PathList, CheckedCollection]] = [
        ([], mapping),
    ]

    for path, dict_or_list in queue:  # type: PathList, CheckedCollection
        if anchor := anchor_getter(dict_or_list):
            _errors = _run_all_actions(mapping, path, anchor, actions)
            errors.extend(_errors)
        elif isinstance(dict_or_list, dict):
            for key_or_index, value in dict_or_list.items():
                queue.append((_get_extended_path(path, key_or_index), value))
        elif isinstance(dict_or_list, list):
            for key_or_index, item in enumerate(dict_or_list):
                queue.append((_get_extended_path(path, key_or_index), item))

    if not errors:
        for action in actions:
            errors.extend(action.__post_traversal_hook__(mapping))

    return errors


def _run_all_actions(
    mapping: dict,
    path: PathList,
    anchor: ActionAnchor,
    actions: list[BaseAction],
) -> list:
    errors: list = []

    # check that actions have different types
    action_types = [action.action_type for action in actions]
    unique_action_types = set(action_types)
    if len(action_types) != len(unique_action_types):
        raise ActionException("Need unique action types for actions")

    for action in actions:  # type: BaseAction
        try:
            transformed_value = action.get_value(path, anchor)
        except ActionException as err:
            errors.append(str(err))
        else:
            if isinstance(transformed_value, MissedValue):
                continue
            change_value_in_mapping(mapping, transformed_value, path)

    return errors


def _get_extended_path(path_list: PathList, new_value: str | int) -> PathList:
    new_path_list = list(path_list)
    new_path_list.append(new_value)
    return new_path_list
