"""Names and lifecycle states of the Cutover Job node."""

from enum import StrEnum


CUTOVER_JOB_LABEL = "CutoverJob"
CUTOVER_JOB_STATUS_INDEX = "cutover_job_status_index"


class CutoverJobStatus(StrEnum):
    """Lifecycle phase of a Cutover Job."""

    PENDING = "pending"
    ROLLING_BACK = "rolling_back"
    COMMITTED = "committed"
    CLEANING = "cleaning"
    DONE = "done"
    ROLLED_BACK = "rolled_back"
