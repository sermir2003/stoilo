DROP TABLE IF EXISTS task_data;

CREATE TABLE task_data (
  task_id                     VARCHAR(32)   NOT NULL         COMMENT 'UUID hex string, primary key',
  call_spec                   LONGBLOB      NOT NULL         COMMENT 'Serialized python function and arguments',
  init_valid_func             LONGBLOB      NOT NULL         COMMENT 'Serialized initial validation function',
  compare_valid_func          LONGBLOB      NOT NULL         COMMENT 'Serialized comparative validation function',
  returned                    LONGBLOB      DEFAULT NULL     COMMENT 'Serialized returned object or Exception',
  task_status                 TINYINT       NOT NULL         COMMENT 'task_service_pb2.TaskStatus integer value',
  result_status               TINYINT       DEFAULT NULL     COMMENT 'task_service_pb2.ResultStatus integer value',
  error_message               TEXT          DEFAULT NULL     COMMENT 'System error message if any',
  created_at                  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at                  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (task_id)
) COMMENT = 'Task data for gRPC task service';
