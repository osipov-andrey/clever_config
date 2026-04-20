import os
from pathlib import Path
from typing import Generator, List, Tuple

import pytest
import yaml

path_to_config: Path = Path(__file__).parent.absolute().joinpath("configs")


@pytest.fixture
def config_file() -> Generator[Tuple[str, List[str]], None, None]:
    file_name = path_to_config.joinpath("config_test.yml")

    config_ = {
        "f1": {"type": "ENV", "value": "VARIABLE_0"},
        "f2": {
            "s1": ["foo", "bar"],
        },
        "f3": {"s1": {"t1": {"type": "ENV", "value": "VARIABLE"}}},
        "f4": {
            "s1": ["a", "", 42],
            "s2": ["d", "f", {"type": "Env", "value": "VARIABLE_2"}],
        },
        "f5": [
            ["kek", {"type": "env", "value": "VARIABLE_3"}],
            {"t1": ["lol", {"type": "ENV", "value": "VARIABLE_4"}]},
        ],
    }
    expected_vars = [
        "VARIABLE_0",
        "VARIABLE",
        "VARIABLE_2",
        "VARIABLE_3",
        "VARIABLE_4",
    ]

    with open(file_name, "w") as f:
        yaml.dump(config_, f)

    yield str(file_name), expected_vars

    os.remove(file_name)


@pytest.fixture
def config_file_with_env(config_file: Tuple[str, List[str]]) -> Generator[Tuple[str, str], None, None]:
    file_name, expected_vars = config_file  # type: str, List[str]

    test_value: str = "TEST"

    for var in expected_vars:
        os.environ[var] = test_value

    yield file_name, test_value

    for var in expected_vars:
        os.environ.pop(var)
        assert os.getenv(var) is None
