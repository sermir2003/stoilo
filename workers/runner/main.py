#!/usr/bin/env python3

import argparse
import json
import logging
import sys
from enum import IntEnum, unique

import cloudpickle

logger = logging.getLogger(__name__)


# Must be the same as ResultStatus in proto/task_service/task_service.proto.
@unique
class ResultStatus(IntEnum):
    SUCCESS = 0
    USER_ERROR = 1
    SYSTEM_ERROR = 2


def make_result(status, returned=None, error=None):
    return {
        "status": status.name,
        "returned": returned,
        "error": error,
    }


def execute(call_spec_path):
    try:
        with open(call_spec_path, "rb") as infile:
            call_spec = cloudpickle.load(infile)
    except Exception as e:
        return make_result(
            ResultStatus.SYSTEM_ERROR,
            error=f"Failed to load call_spec from file: {e}",
        )

    try:
        kwargs = call_spec["kwargs"]
        func = call_spec["func"]
    except Exception as e:
        return make_result(
            ResultStatus.SYSTEM_ERROR,
            error=f"Invalid call_spec structure: {e}",
        )

    try:
        returned = func(**kwargs)
    except Exception as e:
        return make_result(
            ResultStatus.USER_ERROR,
            error=f"Exception in user function: {e}",
        )

    try:
        json.dumps(returned)
    except Exception as e:
        return make_result(
            ResultStatus.USER_ERROR,
            error=f"Failed to serialize returned value to JSON: {e}",
        )

    return make_result(ResultStatus.SUCCESS, returned=returned)


def parse_args():
    parser = argparse.ArgumentParser(description="Execute a Python task on a worker node.")
    parser.add_argument("call_spec_path", help="Path to the file containing serialized function and arguments.")
    parser.add_argument("result_path", help="Path where the serialized result should be written.")
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = parse_args()

    try:
        result = execute(args.call_spec_path)
    except Exception as e:
        logger.critical("Unexpected runner error while executing task: %s", e)
        sys.exit(1)

    try:
        with open(args.result_path, "w", encoding="utf-8") as outfile:
            json.dump(result, outfile, ensure_ascii=False)
    except Exception as e:
        logger.critical("Failed to save result to %s: %s", args.result_path, e)
        sys.exit(1)


if __name__ == "__main__":
    main()
