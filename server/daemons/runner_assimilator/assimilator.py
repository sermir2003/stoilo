import sys
import logging
import json

from gened_proto.task_service.task_service_pb2 import ResultStatus

from .database import database
from .cli_parser import parse_args, ErrorArgs

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger.debug(f"runner_assimilator received args: {sys.argv}")

    args = parse_args()

    task_id = database.get_task_id_for_workunit(args.wu_id)

    logger.debug(f"task_id: {task_id}")

    if isinstance(args, ErrorArgs):
        err_msg = f"BOINC error code: {args.error_code}, see WU_ERROR_* in html/inc/common_defs.inc"

        success = database.set_task_finished(task_id, ResultStatus.SYSTEM_ERROR, error_message=err_msg)

        if not success:
            logger.error(f"Failed to set task {task_id} to FAILED: {err_msg}")
            sys.exit(1)
    else:
        try:
            with open(args.result_file, "r", encoding="utf-8") as f:
                result = json.load(f)
            
            logger.debug(f"Result: {result}")
            result_status = ResultStatus.Value(result["status"])
        except Exception as e:
            logger.error(f"Failed to load result from file {args.result_file}: {e}")
            sys.exit(1)

        if result_status == ResultStatus.SUCCESS:
            returned = json.dumps(result["returned"])
            success = database.set_task_finished(task_id, result_status, returned=returned)
        else:
            error_message = result.get("error", "")
            logger.debug(f"error_message: {error_message}")
            success = database.set_task_finished(task_id, result_status, error_message=error_message)

        if not success:
            logger.error(f"Failed to set task {task_id} to COMPLETED")
            sys.exit(1)
