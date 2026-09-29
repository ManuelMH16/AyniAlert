"""Lazily initialized AWS SDK resources reused within a Lambda environment."""

from __future__ import annotations

from functools import cache
from typing import Any


@cache
def dynamodb_resource() -> Any:
    """Return one DynamoDB resource and connection pool per execution environment."""
    import boto3

    return boto3.resource("dynamodb")
