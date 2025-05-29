import os
import logging
import subprocess

logger = logging.getLogger(__name__)

class WorkCreator:
    def __init__(self, project_dir, tmp_dir):
        self.project_dir = project_dir
        self.tmp_dir = tmp_dir

    def create_work(self, task_id, flavor, call_spec, redundancy_options):
        # Create call_spec file
        call_spec_file_name = f'wu_{task_id}_call_spec'
        call_spec_file_tmp_path = os.path.join(self.tmp_dir, call_spec_file_name)
        with open(call_spec_file_tmp_path, 'wb') as f:
            f.write(call_spec)

        # Stage file for BOINC
        self._run_subprocess(['bin/stage_file', call_spec_file_tmp_path], "Failed to stage file")

        # Create BOINC work
        appname = f'raboshka_{flavor}'
        self._run_subprocess(['bin/create_work',
                                '--appname', appname,
                                '--min_quorum', str(redundancy_options.min_quorum),
                                '--target_nresults', str(redundancy_options.target_nresults),
                                '--max_error_results', str(redundancy_options.max_error_results),
                                '--max_total_results', str(redundancy_options.max_total_results),
                                '--max_success_results', str(redundancy_options.max_success_results),
                                '--delay_bound', str(redundancy_options.delay_bound),
                                '--wu_name', str(task_id),
                                '--wu_template', 'templates/raboshka/2.0/in',
                                '--result_template', 'templates/raboshka/2.0/out',
                                call_spec_file_name
                                ], "Failed to create BOINC work")

    def _run_subprocess(self, cmd, error_prefix):
        """Run a subprocess command with proper error handling."""
        logger.debug(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                text=True
            )
            logger.debug(f"Command inished with exit code {result.returncode}")
            return result
        except subprocess.CalledProcessError as e:
            error_msg = f"{error_prefix}: {e}"
            if e.stdout:
                error_msg += f"\nStdout: {e.stdout}"
            if e.stderr:
                error_msg += f"\nStderr: {e.stderr}"
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"{error_prefix}: {e}"
            raise RuntimeError(error_msg)
