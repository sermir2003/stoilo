import os
import logging
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager

from gened_proto.task_service import task_service_pb2

from .utils import get_env_or_die

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            pool_size = int(get_env_or_die('TASK_SERVICE_POOL_SIZE'))
            self.pool = pooling.MySQLConnectionPool(
                pool_name="task_service_pool",
                pool_size=pool_size,
                host=get_env_or_die('DB_HOST'),
                port=int(get_env_or_die('DB_PORT')),
                user=get_env_or_die('DB_USER'),
                password=get_env_or_die('DB_PASSWORD'),
                database=get_env_or_die('DB_NAME'),
                charset='utf8mb4',
                autocommit=False
            )
            logger.info(f"Database connection pool initialized with size {pool_size}")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = self.pool.get_connection()
            yield conn
        except mysql.connector.Error as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass  # Already in error state, ignore rollback failures
            logger.error(f"Database connection error: {e}")
            raise
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass  # Already in error state, ignore rollback failures
            logger.error(f"Unexpected error in database operation: {e}")
            raise
        else:
            if conn and not conn.autocommit:
                conn.commit()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error while closing connection: {e}")
    
    @contextmanager
    def get_cursor(self, dictionary=True):
        with self.get_connection() as conn:
            cursor = None
            try:
                cursor = conn.cursor(dictionary=dictionary)
                yield cursor
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception as e:
                        logger.warning(f"Error while closing cursor: {e}")
    
    def create_task(self, task_id, call_spec, init_valid_func, compare_valid_func, task_status):
        try:
            with self.get_cursor() as cursor:
                query = """
                INSERT INTO task_data (
                    task_id, call_spec, init_valid_func, compare_valid_func, task_status
                ) VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (task_id, call_spec, init_valid_func, compare_valid_func, task_status))
                logger.info(f"Created task {task_id} in database")
                return True
        except (mysql.connector.Error, Exception) as e:
            logger.error(f"Database error creating task {task_id}: {e}")
            return False
    
    def set_task_failed(self, task_id, error_message):
        task_status = task_service_pb2.TaskStatus.FINISHED
        result_status = task_service_pb2.ResultStatus.SYSTEM_ERROR
        try:
            with self.get_cursor() as cursor:
                query = """
                UPDATE task_data
                SET task_status = %s, result_status = %s, error_message = %s
                WHERE task_id = %s
                """
                cursor.execute(query, (task_status, result_status, error_message, task_id))
                logger.info(f"Set task {task_id} to FAILED: {error_message}")
                return True
        except (mysql.connector.Error, Exception) as e:
            logger.error(f"Database error setting task {task_id} to FAILED: {e}")
            return False
    
    def get_task_status(self, task_id):
        try:
            with self.get_cursor() as cursor:
                query = """
                SELECT returned, task_status, result_status, error_message
                FROM task_data
                WHERE task_id = %s
                """
                cursor.execute(query, (task_id,))
                row = cursor.fetchone()
                if row:
                    logger.info(f"Retrieved task {task_id} from database")
                else:
                    logger.info(f"Task {task_id} not found in database")
                return row
        except (mysql.connector.Error, Exception) as e:
            logger.error(f"Database error retrieving task {task_id}: {e}")
            return None

# Singleton
database = Database()
