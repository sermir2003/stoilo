import argparse
import sys
import logging
import cloudpickle
import json
from enum import IntEnum, unique

logger = logging.getLogger(__name__)

# must be the same as ResultStatus in the proto/task_service/task_service.proto
# (do not want to add dependency and import proto only for this Enum)
@unique
class ResultStatus(IntEnum):
    SUCCESS = 0
    USER_ERROR = 1
    SYSTEM_ERROR = 2


def execute(call_spec_path):
    try:
        with open(call_spec_path, "rb") as infile:
            call_spec = cloudpickle.load(infile)
    except Exception as e:
        error_message = f"Failed to load call_spec from the file: {e}"
        return ResultStatus.SYSTEM_ERROR, error_message

    kwargs = call_spec["kwargs"]
    func = call_spec["func"]

    try:
        returned = func(kwargs)
    except Exception as e:
        error_message = f"Exception is thrown in user function: {e}"
        return ResultStatus.USER_ERROR, error_message

    try:
        serialized_returned = json.dumps(returned)
    except Exception as e:
        error_message = f"Failed to serialize returned value to json: {e}"
        return ResultStatus.USER_ERROR, error_message

    return ResultStatus.SUCCESS, serialized_returned


def save_result(result_path, status, serialized_result):
    with open(result_path, "w") as outfile:
        outfile.write(str(status))
        outfile.write(serialized_result)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute a Python task on a worker node."
    )
    parser.add_argument(
        "call_spec_path",
        help="Path to the file containing serialized function and arguments."
    )
    parser.add_argument(
        "result_path",
        help="Path where the serialized result should be written."
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    args = parse_args()

    try:
        status, serialized_result = execute(args.call_spec_path)
        save_result(args.result_path, status, serialized_result)
    except Exception as e:
        logger.critical(f"Unexpected raboshka error: {e}")
        sys.exit(1)
