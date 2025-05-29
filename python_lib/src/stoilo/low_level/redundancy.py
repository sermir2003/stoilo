from typing import Optional

from gened_proto.task_service import task_service_pb2

def CreateOptions(
        min_quorum: Optional[int] = None,
        target_nresults: Optional[int] = None,
        max_error_results: Optional[int] = None,
        max_total_results: Optional[int] = None,
        max_success_results: Optional[int] = None,
        delay_bound: Optional[int] = None) -> task_service_pb2.RedundancyOptions:
    if min_quorum is None:
        min_quorum = 2

    if target_nresults is None:
        target_nresults = min_quorum
    elif target_nresults < min_quorum:
        raise ValueError(f"target_nresults must be at least min_quorum, got {target_nresults} and {min_quorum}")

    if max_total_results is None:
        max_total_results = 3

    if max_error_results is None:
        max_error_results = max_total_results - (min_quorum // 2 + 1)
        # otherwise it is impossible to collect strict majority from min_quorum
    if max_error_results == 0:  # 0 is not allowed by BOINC
        max_error_results = 1

    if max_success_results is None:
        max_success_results = max_total_results

    if delay_bound is None:
        delay_bound = 300  # 5 minutes

    return task_service_pb2.RedundancyOptions(
        min_quorum=min_quorum,
        target_nresults=target_nresults,
        max_error_results=max_error_results,
        max_total_results=max_total_results,
        max_success_results=max_success_results,
        delay_bound=delay_bound
    )

TRIVIAL_OPTIONS = CreateOptions(
    min_quorum=1,
    target_nresults=1,
    max_error_results=0,
    max_total_results=1,
    max_success_results=1
)

CLASSIC_OPTIONS = CreateOptions()
