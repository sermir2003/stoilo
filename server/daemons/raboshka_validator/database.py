import mysql.connector
import logging
import cloudpickle
from typing import Callable
from contextlib import contextmanager

from .utils import get_env_or_die

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
    def cursor(self, commit=True, dictionary=True):
        connection = self._get_connection()
        cursor = None
        try:
            cursor = connection.cursor(dictionary=dictionary)
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
                cursor.close()
    
    def close(self):
        if self._connection and self._connection.is_connected():
            try:
                self._connection.close()
                logger.debug("Database connection closed")
            except mysql.connector.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._connection = None
    
    def get_task_id_for_result(self, result_id: int) -> str:
        try:
            with self.cursor() as cursor:
                query1 = "SELECT workunitid FROM result WHERE id = %s"
                cursor.execute(query1, (result_id,))
                result1 = cursor.fetchone()
                if not result1:
                    logger.warning(f"No result found with result_id {result_id}")
                    raise ValueError(f"No result found with result_id {result_id}")
                workunit_id = result1['workunitid']

                query2 = "SELECT name FROM workunit WHERE id = %s"
                cursor.execute(query2, (workunit_id,))
                result2 = cursor.fetchone()
                if not result2:
                    logger.warning(f"No workunit found with workunit_id {workunit_id}")
                    raise ValueError(f"No workunit found with workunit_id {workunit_id}")
                task_id = result2['name']
                
                logger.info(f"Retrieved task_id {task_id} for result_id {result_id}")
                return task_id
        except mysql.connector.Error as e:
            logger.error(f"Database error when retrieving task_id for result {result_id}: {e}")
            raise
    
    def get_validation_func(self, task_id: str, mode: str) -> bytes:
        try:
            with self.cursor(dictionary=False) as cursor:
                if mode == 'init':
                    column = 'init_valid_func'
                elif mode == 'compare':
                    column = 'compare_valid_func'
                else:
                    raise ValueError(f"Invalid validation mode: {mode}")
                
                query = f"SELECT {column} FROM task_data WHERE task_id = %s"
                cursor.execute(query, (task_id,))
                result = cursor.fetchone()
                if not result or not result[0]:
                    logger.warning(f"No validation function found for task_id {task_id} and mode {mode}")
                    raise ValueError(f"No validation function found for task_id {task_id} and mode {mode}")

                logger.info(f"Retrieved validation function for task_id {task_id}, mode {mode}")
                return result[0]
        except mysql.connector.Error as e:
            logger.error(f"Database error when retrieving validation function for task {task_id}: {e}")
            raise
    
    def __del__(self):
        self.close()

# Singleton
database = Database()
