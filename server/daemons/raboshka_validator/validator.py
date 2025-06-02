import sys
import argparse
import cloudpickle
import json
import logging
from enum import IntEnum, unique

from gened_proto.task_service.task_service_pb2 import ResultStatus

from .database import database

logger = logging.getLogger(__name__)


# About exit codes read https://github.com/BOINC/boinc/wiki/Validators-in-scripting-languages
@unique
class ExitCode(IntEnum):
    ACCEPTED = 0            # approved by the validator
    REJECTED = 1            # rejected by the validator
    OTHER_ERROR = 2         # any other error, no retries, validation failed
    TEMP_ERROR = 3          # temporary error, retry later
    VALID_FUNC_ERROR = 4    # error in the validation function, is considered the user's fault,
                            # no retries, validation failed


def parse_args():
    parser = argparse.ArgumentParser(
        description="BOINC validator: initial or comparative validation"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--init',
        nargs=2,
        metavar=('RESULT_ID', 'FILE'),
        help='Initialize with a result ID and output file'
    )
    group.add_argument(
        '--compare',
        nargs=4,
        metavar=('RESULT_ID_1', 'FILE_1', 'RESULT_ID_2', 'FILE_2'),
        help='Compare two results with their corresponding files'
    )
    try:
        return parser.parse_args()
    except Exception as e:
        logger.error(f"Failed to parse arguments: {e}")
        sys.exit(ExitCode.OTHER_ERROR)


def get_valid_func(task_id, mode):
    valid_func_blob = database.get_validation_func(task_id, mode)
    try:
        valid_func = cloudpickle.loads(valid_func_blob)
    except Exception as e:
        logger.error(f"Failed to deserialize validation function for task_id {task_id}: {e}")
        sys.exit(ExitCode.VALID_FUNC_ERROR)
    return valid_func


def deserialize_result(filepath):
    try:
        with open(filepath, 'r') as f:
            str_result_status = f.read(1)
            serialized_result = f.read()

        # logger.debug(f"result_status: {str_result_status} serialized_result: {serialized_result}")

        result_status = int(str_result_status)
        assert result_status in [ResultStatus.SUCCESS, ResultStatus.USER_ERROR, ResultStatus.SYSTEM_ERROR]
        if result_status == ResultStatus.SUCCESS:
            result = json.loads(serialized_result)
        else:
            result = serialized_result

        return result_status, result
    except Exception as e:
        logger.error(f"(This could be an attack) Failed to load result: {e}; rejected")
        sys.exit(ExitCode.REJECTED)


def initial_validation(task_id, valid_func,
                       result_id, result_status, result):
    if result_status == ResultStatus.USER_ERROR:
        logger.info(f"Initial validation: result_id {result_id} for task_id {task_id} is USER_ERROR; accepted")
        sys.exit(ExitCode.ACCEPTED)

    if result_status == ResultStatus.SYSTEM_ERROR:
        logger.info(f"Initial validation: result_id {result_id} for task_id {task_id} is SYSTEM_ERROR; rejected")
        sys.exit(ExitCode.REJECTED)

    try:
        is_valid = valid_func(result)
    except Exception as e:
        logger.info(f"Error during executing initial validation function: {e}")
        sys.exit(ExitCode.VALID_FUNC_ERROR)

    if not isinstance(is_valid, bool):
        logger.info(f"Validation function returned non-boolean value: {is_valid}")
        sys.exit(ExitCode.VALID_FUNC_ERROR)

    if is_valid:
        logger.info(f"Initial validation: result_id {result_id} for task_id {task_id} is accepted")
        sys.exit(ExitCode.ACCEPTED)

    logger.info(f"Initial validation: result_id {result_id} for task_id {task_id} is rejected")
    sys.exit(ExitCode.REJECTED)


def comparative_validation(task_id, valid_func,
                           result_id_1, result_status_1, result_1,
                           result_id_2, result_status_2, result_2):
    if result_status_1 == ResultStatus.USER_ERROR and result_status_2 == ResultStatus.USER_ERROR:
        logger.info(f"Comparative validation: result_id {result_id_1} and {result_id_2} for task_id {task_id} "
                    "are both USER_ERROR; considered equal")
        sys.exit(ExitCode.ACCEPTED)

    if result_status_1 == ResultStatus.USER_ERROR or result_status_2 == ResultStatus.USER_ERROR:
        logger.info(f"Comparative validation: among result_id {result_id_1} and {result_id_2} for task_id {task_id} "
                    "there is exactly one USER_ERROR; considered different")
        sys.exit(ExitCode.REJECTED)

    try:
        are_equal = valid_func(result_1, result_2)
    except Exception as e:
        logger.info(f"Error during comparative validation: {e}")
        sys.exit(ExitCode.VALID_FUNC_ERROR)

    if not isinstance(are_equal, bool):
        logger.info(f"Validation function returned non-boolean value: {are_equal}")
        sys.exit(ExitCode.VALID_FUNC_ERROR)

    if are_equal:
        logger.info(f"Comparative validation: result_id {result_id_1} and {result_id_2} for task_id {task_id} are equal")
        sys.exit(ExitCode.ACCEPTED)

    logger.info(f"Comparative validation: result_id {result_id_1} and {result_id_2} for task_id {task_id} are different")
    sys.exit(ExitCode.REJECTED)


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger.debug(f"raboshka_validator received args: {sys.argv}")

    args = parse_args()

    try:
        if args.init:
            result_id, file_path = args.init
            task_id = database.get_task_id_for_result(result_id)
            logger.debug(f"task_id: {task_id}")
            valid_func = get_valid_func(task_id, 'init')
            result_status, result = deserialize_result(file_path)
            initial_validation(task_id, valid_func,
                               result_id, result_status, result)
        elif args.compare:
            result_id_1, file_1, result_id_2, file_2 = args.compare
            task_id = database.get_task_id_for_result(result_id_1)
            logger.debug(f"task_id: {task_id}")
            valid_func = get_valid_func(task_id, 'compare')
            result_status_1, result_1 = deserialize_result(file_1)
            result_status_2, result_2 = deserialize_result(file_2)
            comparative_validation(task_id, valid_func,
                                   result_id_1, result_status_1, result_1,
                                   result_id_2, result_status_2, result_2)
    except Exception as e:
        logger.error(f"Unknown internal error: {e}")
        sys.exit(ExitCode.OTHER_ERROR)
