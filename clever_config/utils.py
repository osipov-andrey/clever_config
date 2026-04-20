from typing import Any, List, Union

KeyOrIndex = Union[str, int]


class IncompatiblePathAndMappingException(Exception):
    pass


def change_value_in_mapping(mapping: dict, value: Any, path: List[KeyOrIndex]) -> None:
    if len(path) == 0:
        pass
    elif len(path) == 1:
        mapping[path[0]] = value
    else:
        step = path[0]
        rest_path = path[1:]
        try:
            change_value_in_mapping(mapping[step], value, rest_path)
        except (KeyError, IndexError):
            raise IncompatiblePathAndMappingException(f"Wrong path: {path}")
