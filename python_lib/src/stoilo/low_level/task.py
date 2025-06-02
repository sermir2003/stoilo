import asyncio
import cloudpickle
import json
import logging
from typing import Any, Dict, Callable, Optional

from gened_proto.task_service import task_service_pb2

import stoilo
from stoilo.low_level.task_result import TaskResult, UserError, SystemError

logger = logging.getLogger(__name__)

class SubmittedTask:
    def __init__(self,
                 connection: 'Connection',
                 task_id: str):
        self._connection = connection
        self._task_id = task_id

    @property
    def task_id(self) -> Optional[str]:
        return self._task_id

    async def result(self) -> TaskResult:
        polling_config = self._connection.network_config.polling
        delay = polling_config.initial_delay
        attempts = 0
        request = task_service_pb2.PollTaskRequest(task_id=self._task_id)

        while attempts < polling_config.max_attempts:
            poll_response = await self._connection._poll_task(request)

            if not poll_response.found:
                logger.warning(f"Task {self._task_id} not found on the server")

            elif poll_response.task_status == task_service_pb2.TaskStatus.FINISHED:
                if poll_response.result_status == task_service_pb2.ResultStatus.SUCCESS:
                    return json.loads(poll_response.returned.decode('utf-8'))
                elif poll_response.result_status == task_service_pb2.ResultStatus.USER_ERROR:
                    return UserError(poll_response.error_message)
                elif poll_response.result_status == task_service_pb2.ResultStatus.SYSTEM_ERROR:
                    return SystemError(poll_response.error_message)
                raise ValueError(f"Unknown result status: {poll_response.result_status}")
            
            await asyncio.sleep(delay)
            
            delay = min(
                delay * polling_config.multiplier,
                polling_config.max_delay
            )
            attempts += 1

        return SystemError(f"Task polling timed out after {attempts} attempts")


class StagedTask:
    def __init__(self,
                 connection: 'Connection',
                 kwargs: Optional[Dict[str, Any]] = None,
                 func: Optional[Callable[[Dict[str, Any]], Any]] = None,
                 init_valid_func: Optional[Callable[[Any], bool]] = None,
                 compare_valid_func: Optional[Callable[[Any, Any], bool]] = None,
                 flavor: Optional[str] = None,
                 redundancy_options: Optional[task_service_pb2.RedundancyOptions] = None):
        if kwargs is None:
            kwargs = {}
        if func is None:
            raise ValueError("func must be provided")
        if init_valid_func is None:
            init_valid_func = lambda _: True
        if compare_valid_func is None:
            compare_valid_func = lambda x, y: x == y
        if flavor is None:
            flavor = stoilo.low_level.flavors.DEFAULT
        if redundancy_options is None:
            redundancy_options = stoilo.low_level.redundancy.CreateOptions()

        self._connection = connection
        self._flavor = flavor
        self._call_spec = cloudpickle.dumps({
            "kwargs": kwargs,
            "func": func,
        })
        self._init_valid_func = cloudpickle.dumps(init_valid_func)
        self._compare_valid_func = cloudpickle.dumps(compare_valid_func)
        self._redundancy_options = redundancy_options

    @property
    def task_id(self) -> Optional[str]:
        return None

    async def submit(self) -> SubmittedTask:
        request = task_service_pb2.CreateTaskRequest(
            flavor=self._flavor,
            call_spec=self._call_spec,
            init_valid_func=self._init_valid_func,
            compare_valid_func=self._compare_valid_func,
            redundancy_options=self._redundancy_options,
        )
        response = await self._connection._create_task(request)
        return SubmittedTask(self._connection, task_id=response.task_id)

    async def result(self) -> TaskResult:
        submitted = await self.submit()
        result = await submitted.result()
        return result
