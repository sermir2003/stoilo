from typing import Any, Union

class UserError(Exception):
    def __str__(self) -> str:
        return f"Stoilo user error: {super().__str__()}"

class SystemError(Exception):
    def __str__(self) -> str:
        return f"Stoilo system error: {super().__str__()}"

TaskResult = Union[Any, UserError, SystemError]
