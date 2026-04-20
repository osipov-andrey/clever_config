

### Ho to use

```python
from pprint import pprint

from clever_config.dict_traversal import dict_traversal
from clever_config.actions import KMSAction

user_config = {
    "my_service": {
        "url": "https://my_service.com",
        "user": "my_service_user",
        "password": {
            "type": "KNS",
            "value": "AQICAHhV4l..."
        },
    }
}

if __name__ == '__main__':
    dict_traversal(user_config, [KMSAction()])
    pprint(user_config)
```
Result:
```shell
{ 'ads': { 'password': 'password',
           'url': 'https://my_service.com',
           'user': 'my_service_user'}}
```
Look all available [ACTIONS](./docs/actions.md)

### How to publish

```shell
poetry build
poetry publish
```
