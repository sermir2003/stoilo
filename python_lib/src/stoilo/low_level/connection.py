import grpc
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

from gened_proto.task_service import task_service_pb2, task_service_pb2_grpc

from .task import StagedTask, SubmittedTask


@dataclass
class PollingConfig:
    """Configuration for the task polling mechanism."""
    max_attempts:  int   = 100    # Maximum number of polling attempts
    initial_delay: float = 15     # Initial delay between polls in seconds
    max_delay:     float = 60     # Maximum delay between polls in seconds
    multiplier:    float = 1.1    # Multiplier for delay after each poll attempt


@dataclass
class NetworkConfig:
    """Network configuration for the connection."""
    timeout: float         = 30.0                                  # RPC timeout in seconds
    polling: PollingConfig = field(default_factory=PollingConfig)  # Polling configuration


class Connection:
    def __init__(self, address: str, network_config: Optional[NetworkConfig] = None):
        self.address = address
        self.channel = None
        self.stub = None
        self.network_config = network_config or NetworkConfig()

    async def connect(self) -> None:
        if self.channel is None:
            self.channel = grpc.aio.insecure_channel(
                target=self.address,
                options=[
                    ('grpc.max_send_message_length', 1024 * 1024 * 1024),
                    ('grpc.max_receive_message_length', 1024 * 1024 * 1024),
                ],
            )
            self.stub = task_service_pb2_grpc.TaskServiceStub(self.channel)
    
    async def close(self) -> None:
        if self.channel is not None:
            await self.channel.close()
            self.channel = None
            self.stub = None
    
    async def _create_task(self, request: task_service_pb2.CreateTaskRequest) -> task_service_pb2.CreateTaskResponse:
        """Create a task on the server."""
        await self.connect()
        timeout = self.network_config.timeout
        return await self.stub.CreateTask(request, timeout=timeout)
    
    async def _poll_task(self, request: task_service_pb2.PollTaskRequest) -> task_service_pb2.PollTaskResponse:
        """Poll for task status and results."""
        await self.connect()
        timeout = self.network_config.timeout
        return await self.stub.PollTask(request, timeout=timeout)
    
    def create_task(self, **kwargs) -> StagedTask:
        return StagedTask(self, **kwargs)

    def restore_task(self, task_id: str) -> SubmittedTask:
        return SubmittedTask(self, task_id)


async def connect(address: str, network_config: Optional[NetworkConfig] = None) -> Connection:
    conn = Connection(address, network_config)
    await conn.connect()
    return conn
