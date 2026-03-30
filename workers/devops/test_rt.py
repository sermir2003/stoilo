#!/usr/bin/env python3

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# Each payload must be:
#   base64.b64encode(cloudpickle.dumps(call_spec)).decode("ascii")
#
# where call_spec is exactly:
#   {
#       "func": <callable>,
#       "kwargs": <dict>,
#   }
#
# Serialize these payloads yourself under Python 3.12.3 with the exact
# cloudpickle version of the tested runtime.
#
# Suggested serialized objects:
#
# 1) const_hello
#    {
#        "func": lambda: "hello",
#        "kwargs": {},
#    }
#
# 2) sum_ints
#    {
#        "func": lambda a, b: a + b,
#        "kwargs": {"a": 2, "b": 3},
#    }
#
# 3) numpy_sum
#    {
#        "func": lambda xs: __import__("numpy").sum(xs).item(),
#        "kwargs": {"xs": [1, 2, 3]},
#    }
#
# 4) torch_tensor_sum
#    {
#        "func": lambda xs: __import__("torch").tensor(xs).sum().item(),
#        "kwargs": {"xs": [1, 2, 3]},
#    }

TEST_CASES = [
    {
        "name": "const_hello",
        "call_spec_b64": "gAWVwQEAAAAAAAB9lCiMBGZ1bmOUjBdjbG91ZHBpY2tsZS5jbG91ZHBpY2tsZZSMDl9tYWtlX2Z1bmN0aW9ulJOUKGgCjA1fYnVpbHRpbl90eXBllJOUjAhDb2RlVHlwZZSFlFKUKEsASwBLAEsASwBLA0MElwB5AZROjAVoZWxsb5SGlCkpjAc8c3RkaW4+lIwIPGxhbWJkYT6UjAg8bGFtYmRhPpRLAUMCgQCUQwCUKSl0lFKUfZQojAtfX3BhY2thZ2VfX5ROjAhfX25hbWVfX5SMCF9fbWFpbl9flHVOTk50lFKUaAKMEl9mdW5jdGlvbl9zZXRzdGF0ZZSTlGgZfZR9lChoFowIPGxhbWJkYT6UjAxfX3F1YWxuYW1lX1+UjAg8bGFtYmRhPpSMD19fYW5ub3RhdGlvbnNfX5R9lIwOX19rd2RlZmF1bHRzX1+UTowMX19kZWZhdWx0c19flE6MCl9fbW9kdWxlX1+UaBeMB19fZG9jX1+UTowLX19jbG9zdXJlX1+UTowXX2Nsb3VkcGlja2xlX3N1Ym1vZHVsZXOUXZSMC19fZ2xvYmFsc19flH2UdYaUhlIwjAZrd2FyZ3OUfZR1Lg==",
        "expected_status": "SUCCESS",
        "expected_result": "hello",
    },
    {
        "name": "sum_ints",
        "call_spec_b64": "gAWV3AEAAAAAAAB9lCiMBGZ1bmOUjBdjbG91ZHBpY2tsZS5jbG91ZHBpY2tsZZSMDl9tYWtlX2Z1bmN0aW9ulJOUKGgCjA1fYnVpbHRpbl90eXBllJOUjAhDb2RlVHlwZZSFlFKUKEsCSwBLAEsCSwJLA0MMlwB8AHwBegAAAFMAlE6FlCmMAWGUjAFilIaUjAc8c3RkaW4+lIwIPGxhbWJkYT6UjAg8bGFtYmRhPpRLAUMKgACgIaBhoSWAAJRDAJQpKXSUUpR9lCiMC19fcGFja2FnZV9flE6MCF9fbmFtZV9flIwIX19tYWluX1+UdU5OTnSUUpRoAowSX2Z1bmN0aW9uX3NldHN0YXRllJOUaBt9lH2UKGgYjAg8bGFtYmRhPpSMDF9fcXVhbG5hbWVfX5SMCDxsYW1iZGE+lIwPX19hbm5vdGF0aW9uc19flH2UjA5fX2t3ZGVmYXVsdHNfX5ROjAxfX2RlZmF1bHRzX1+UTowKX19tb2R1bGVfX5RoGYwHX19kb2NfX5ROjAtfX2Nsb3N1cmVfX5ROjBdfY2xvdWRwaWNrbGVfc3VibW9kdWxlc5RdlIwLX19nbG9iYWxzX1+UfZR1hpSGUjCMBmt3YXJnc5R9lChoDEsCaA1LA3V1Lg==",
        "expected_status": "SUCCESS",
        "expected_result": 5,
    },
    {
        "name": "numpy_sum",
        "call_spec_b64": "gAWVWgIAAAAAAAB9lCiMBGZ1bmOUjBdjbG91ZHBpY2tsZS5jbG91ZHBpY2tsZZSMDl9tYWtlX2Z1bmN0aW9ulJOUKGgCjA1fYnVpbHRpbl90eXBllJOUjAhDb2RlVHlwZZSFlFKUKEsBSwBLAEsBSwNLA0NSlwB0AQAAAAAAAAAAZAGrAQAAAAAAAGoDAAAAAAAAAAAAAAAAAAAAAAAAfACrAQAAAAAAAGoFAAAAAAAAAAAAAAAAAAAAAAAAqwAAAAAAAABTAJROjAVudW1weZSGlIwKX19pbXBvcnRfX5SMA3N1bZSMBGl0ZW2Uh5SMAnhzlIWUjAc8c3RkaW4+lIwIPGxhbWJkYT6UjAg8bGFtYmRhPpRLAUMfgACkCqg30yAz1yA30SA3uALTIDvXIEDRIEDTIEKAAJRDAJQpKXSUUpR9lCiMC19fcGFja2FnZV9flE6MCF9fbmFtZV9flIwIX19tYWluX1+UdU5OTnSUUpRoAowSX2Z1bmN0aW9uX3NldHN0YXRllJOUaB99lH2UKGgcjAg8bGFtYmRhPpSMDF9fcXVhbG5hbWVfX5SMCDxsYW1iZGE+lIwPX19hbm5vdGF0aW9uc19flH2UjA5fX2t3ZGVmYXVsdHNfX5ROjAxfX2RlZmF1bHRzX1+UTowKX19tb2R1bGVfX5RoHYwHX19kb2NfX5ROjAtfX2Nsb3N1cmVfX5ROjBdfY2xvdWRwaWNrbGVfc3VibW9kdWxlc5RdlIwLX19nbG9iYWxzX1+UfZR1hpSGUjCMBmt3YXJnc5R9lGgRXZQoSwFLAksDZXN1Lg==",
        "expected_status": "SUCCESS",
        "expected_result": 6,
    },
    {
        "name": "torch_tensor_sum",
        "call_spec_b64": "gAWViQIAAAAAAAB9lCiMBGZ1bmOUjBdjbG91ZHBpY2tsZS5jbG91ZHBpY2tsZZSMDl9tYWtlX2Z1bmN0aW9ulJOUKGgCjA1fYnVpbHRpbl90eXBllJOUjAhDb2RlVHlwZZSFlFKUKEsBSwBLAEsBSwNLA0NulwB0AQAAAAAAAAAAZAGrAQAAAAAAAGoDAAAAAAAAAAAAAAAAAAAAAAAAfACrAQAAAAAAAGoFAAAAAAAAAAAAAAAAAAAAAAAAqwAAAAAAAABqBwAAAAAAAAAAAAAAAAAAAAAAAKsAAAAAAAAAUwCUTowFdG9yY2iUhpQojApfX2ltcG9ydF9flIwGdGVuc29ylIwDc3VtlIwEaXRlbZR0lIwCeHOUhZSMBzxzdGRpbj6UjAg8bGFtYmRhPpSMCDxsYW1iZGE+lEsBQyiAAKQKqDfTIDPXIDrRIDq4MtMgPtcgQtEgQtMgRNcgSdEgSdMgS4AAlEMAlCkpdJRSlH2UKIwLX19wYWNrYWdlX1+UTowIX19uYW1lX1+UjAhfX21haW5fX5R1Tk5OdJRSlGgCjBJfZnVuY3Rpb25fc2V0c3RhdGWUk5RoIH2UfZQoaB2MCDxsYW1iZGE+lIwMX19xdWFsbmFtZV9flIwIPGxhbWJkYT6UjA9fX2Fubm90YXRpb25zX1+UfZSMDl9fa3dkZWZhdWx0c19flE6MDF9fZGVmYXVsdHNfX5ROjApfX21vZHVsZV9flGgejAdfX2RvY19flE6MC19fY2xvc3VyZV9flE6MF19jbG91ZHBpY2tsZV9zdWJtb2R1bGVzlF2UjAtfX2dsb2JhbHNfX5R9lHWGlIZSMIwGa3dhcmdzlH2UaBJdlChLAUsCSwNlc3Uu",
        "expected_status": "SUCCESS",
        "expected_result": 6,
    },
]


def run_case(worker_bin: Path, case: dict) -> tuple[bool, str]:
    if not case["call_spec_b64"]:
        return False, f'{case["name"]}: empty call_spec_b64'

    with tempfile.TemporaryDirectory(prefix=f'test_{case["name"]}_') as tmp:
        tmp_dir = Path(tmp)
        call_spec_path = tmp_dir / "call_spec.bin"
        result_path = tmp_dir / "result.json"

        call_spec_path.write_bytes(base64.b64decode(case["call_spec_b64"]))

        proc = subprocess.run(
            [str(worker_bin), str(call_spec_path), str(result_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if proc.returncode != 0:
            return (
                False,
                f'{case["name"]}: worker exited with code {proc.returncode}\n'
                f'stdout:\n{proc.stdout}\n'
                f'stderr:\n{proc.stderr}'
            )

        if not result_path.exists():
            return False, f'{case["name"]}: result file was not created'

        try:
            with open(result_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            return False, f'{case["name"]}: failed to parse result json: {e}'

        actual_status = payload.get("status")
        if actual_status != case["expected_status"]:
            return (
                False,
                f'{case["name"]}: unexpected status: expected {case["expected_status"]}, got {actual_status}; '
                f'payload={payload}'
            )

        actual_result = payload.get("returned")
        if actual_result != case["expected_result"]:
            return (
                False,
                f'{case["name"]}: unexpected result: expected {case["expected_result"]!r}, got {actual_result!r}; '
                f'payload={payload}'
            )

        return True, f'{case["name"]}: ok'


def main():
    parser = argparse.ArgumentParser(description="Run embedded call_spec tests against a previously built worker binary")
    parser.add_argument("worker_bin", help="Path to previously built worker binary")
    args = parser.parse_args()

    worker_bin = Path(args.worker_bin).expanduser().resolve()
    if not worker_bin.exists():
        print(f"Worker binary does not exist: {worker_bin}", file=sys.stderr)
        sys.exit(1)

    failed = False
    for case in TEST_CASES:
        ok, message = run_case(worker_bin, case)
        print(message)
        if not ok:
            failed = True

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
