import sys
import logging
from dataclasses import dataclass
from typing import List, Union

logger = logging.getLogger(__name__)


@dataclass
class SuccessArgs:
    wu_id: int
    result_file: str


@dataclass
class ErrorArgs:
    error_code: int
    wu_name: str
    wu_id: int


def parse_args() -> Union[SuccessArgs, ErrorArgs]:
    """
    Parse command-line arguments.
    Success variant: <script> wu_id <result_file>
    Error variant: <script> --error <error_code> <wu_name> <wu_id> <runtime>
    """
    try:
        args = sys.argv[1:]
        if not args:
            raise ValueError("No arguments provided")

        if args[0] == "--error":
            if len(args) != 5:
                raise ValueError(
                    "Error variant requires exactly 4 arguments: --error <error_code> <wu_name> <wu_id> <runtime>"
                )
            return ErrorArgs(
                error_code=int(args[1]),
                wu_name=args[2],
                wu_id=int(args[3]),
            )
        else:
            if len(args) != 2:
                raise ValueError(
                    "Success variant requires exactly 2 arguments: wu_id and result_file"
                )
            return SuccessArgs(
                wu_id=int(args[0]),
                result_file=args[1],
            )
    except Exception as e:
        logger.error(f"Failed to parse arguments {args}: {e}")
        sys.exit(1)
