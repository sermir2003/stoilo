import mysql.connector
import logging
from typing import Optional
from contextlib import contextmanager

from .utils import get_env_or_die
from gened_proto.task_service import task_service_pb2

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self._connection = None
    
    def _get_connection(self) -> mysql.connector.connection.MySQLConnection:
        if not self._connection or not self._connection.is_connected():
            try:
                self._connection = mysql.connector.connect(
                    host=get_env_or_die('DB_HOST'),
                    port=int(get_env_or_die('DB_PORT')),
                    user=get_env_or_die('DB_USER'),
                    password=get_env_or_die('DB_PASSWORD'),
                    database=get_env_or_die('DB_NAME'),
                    charset='utf8mb4',
                    autocommit=False
                )
                logger.debug("Created new database connection")
            except mysql.connector.Error as e:
                logger.error(f"Error connecting to MySQL database: {e}")
                raise
        return self._connection
    
    @contextmanager
    def cursor(self, commit=True):
        connection = self._get_connection()
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            yield cursor
            if commit:
                connection.commit()
                logger.debug("Changes committed")
        except mysql.connector.Error as e:
            logger.error(f"Database operation error: {e}")
            connection.rollback()
            logger.debug("Changes rolled back")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as e:
                    logger.warning(f"Error closing cursor: {e}")
    
    def close(self):
        if self._connection and self._connection.is_connected():
            try:
                self._connection.close()
                logger.debug("Database connection closed")
            except mysql.connector.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._connection = None
    
    def get_task_id_for_workunit(self, wu_id: str) -> Optional[str]:
        try:
            with self.cursor(commit=False) as cursor:  # Read-only operation, no commit needed
                query = "SELECT name FROM workunit WHERE id = %s"
                cursor.execute(query, (wu_id,))
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"No workunit found with id {wu_id}")
                    return None
                task_id = result['name']
                logger.info(f"Mapped workunit ID {wu_id} to task_id {task_id}")
                return task_id
        except mysql.connector.Error as e:
            logger.error(f"Database error when retrieving task_id for workunit {wu_id}: {e}")
            return None
    
    def set_task_finished(self, task_id: str,
                          result_status: task_service_pb2.ResultStatus,
                          returned: bytes = b'',
                          error_message: str = "") -> bool:
        task_status = task_service_pb2.TaskStatus.FINISHED
        status_name = f"FINISHED, {task_service_pb2.ResultStatus.Name(result_status)}"
        try:
            with self.cursor() as cursor:
                query = """
                UPDATE task_data
                SET task_status = %s, result_status = %s, returned = %s, error_message = %s
                WHERE task_id = %s
                """
                cursor.execute(query, (task_status, result_status, returned, error_message, task_id))
                if cursor.rowcount == 0:
                    logger.warning(f"No task found with task_id {task_id}")
                    return False
                logger.info(f"Set task {task_id} to {status_name}")
                return True
        except mysql.connector.Error as e:
            logger.error(f"Database error setting task {task_id} to {status_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting task {task_id} to {status_name}: {e}")
            return False
    
    def __del__(self):
        self.close()

# Singleton
database = Database()
