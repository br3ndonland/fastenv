from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, TypedDict, Union

if TYPE_CHECKING:
    import sys

    if sys.version_info < (3, 10):
        from typing_extensions import TypeAlias
    else:
        from typing import TypeAlias

UploadPolicyConditions: TypeAlias = List[Union[Dict[str, str], List[Union[str, int]]]]


class UploadPolicy(TypedDict):
    """Upload policy type for presigned POST to object storage.
    ---

    An upload policy is a security policy with a list of conditions
    under which uploads to an object storage bucket are allowed.
    """

    expiration: str
    conditions: UploadPolicyConditions
