from os import getenv
from typing import List, Optional, Union

from clever_config.actions.base import ActionAnchor, ActionException, BaseAction


class EnvLoaderAction(BaseAction):
    """Just download value from environment variables"""

    action_type = "ENV"

    def _get_value(self, path_chain: List[Union[str, int]], anchor: ActionAnchor) -> str:
        value_: Optional[str] = getenv(anchor.value)
        if not value_:
            raise ActionException(f"Missing ENV Variable: {anchor.value}! Path: {self.path_to_str(path_chain)}")
        return value_
