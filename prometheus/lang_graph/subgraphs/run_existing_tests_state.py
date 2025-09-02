from typing import TypedDict


class RunExistingTestsState(TypedDict):
    testing_patch: str

    test_log: str

    success: bool
