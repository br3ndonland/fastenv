from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typing import TypeAlias

UploadPolicyConditions: TypeAlias = list[dict[str, str] | list[str | int]]


class UploadPolicy(TypedDict):
    """Upload policy type for presigned POST to object storage.
    ---

    An upload policy is a security policy with a list of conditions
    under which uploads to an object storage bucket are allowed.
    """

    expiration: str
    conditions: UploadPolicyConditions
