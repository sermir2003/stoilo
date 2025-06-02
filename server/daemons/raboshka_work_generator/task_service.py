import os
import uuid
import logging
from concurrent import futures

import grpc
from gened_proto.task_service import task_service_pb2, task_service_pb2_grpc

from .utils import get_env_or_die
from .database import database
from .work_creator import WorkCreator

logger = logging.getLogger(__name__)

class TaskService(task_service_pb2_grpc.TaskServiceServicer):
    def __init__(self):
        self.project_dir = get_env_or_die('PROJECT_DIR')
        self.tmp_dir = os.path.join(self.project_dir, 'raboshka_stage_tmp')
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.work_creator = WorkCreator(self.project_dir, self.tmp_dir)

    def CreateTask(self, request, context):
        # Step 1: Generate task_id
        task_id = uuid.uuid4().hex
        logger.info(f"CreateTask request: generated task_id={task_id}")

        # Step 2: Insert task into database
        success = database.create_task(
            task_id=task_id,
            call_spec=request.call_spec,
            init_valid_func=request.init_valid_func,
            compare_valid_func=request.compare_valid_func,
            task_status=task_service_pb2.TaskStatus.RUNNING
        )
        if not success:
            error_msg = "Failed to create task in database"
            logger.error(error_msg)
            context.set_details(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            return task_service_pb2.CreateTaskResponse(task_id="")

        # Step 3: Create BOINC work unit
        try:
            self.work_creator.create_work(task_id, request.flavor, request.call_spec, request.redundancy_options)
            logger.info(f"BOINC work created for task_id={task_id}")
        except Exception as e:
            error_msg = str(e)
            logger.error(error_msg)
            context.set_details(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            # Mark task as failed in database, ignore database errors if any
            database.set_task_failed(task_id, error_message=error_msg)
            return task_service_pb2.CreateTaskResponse(task_id="")

        # Step 4: Return task_id
        return task_service_pb2.CreateTaskResponse(task_id=task_id)

    def PollTask(self, request, context):
        """
        Handle PollTask request:
        Lookup task data in database and return status
        """
        task_id = request.task_id
        logger.info(f"PollTask request received for task_id={task_id}")
        task_data = database.get_task_status(task_id)
        if not task_data:
            return task_service_pb2.PollTaskResponse(found=False)
        return task_service_pb2.PollTaskResponse(
            found=True,
            task_status=task_data['task_status'],
            result_status=task_data['result_status'] or 0,
            returned=task_data['returned'] or b'',
            error_message=task_data['error_message'] or ''
        )


def serve():
    """Start the gRPC server."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    pool_size = int(get_env_or_die('TASK_SERVICE_POOL_SIZE'))
    server = grpc.server(
        thread_pool=futures.ThreadPoolExecutor(max_workers=pool_size),
        options=[
            ('grpc.max_send_message_length', 1024 * 1024 * 1024),
            ('grpc.max_receive_message_length', 1024 * 1024 * 1024),
        ],
    )
    task_service_pb2_grpc.add_TaskServiceServicer_to_server(TaskService(), server)

    bind_addr = f"{get_env_or_die('TASK_SERVICE_HOST')}:{get_env_or_die('TASK_SERVICE_PORT')}"
    server.add_insecure_port(bind_addr)
    logger.info(f"Starting gRPC server at {bind_addr}")
    server.start()
    server.wait_for_termination()
