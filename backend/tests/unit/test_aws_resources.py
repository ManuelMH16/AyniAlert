from types import SimpleNamespace

from ayni_alert.adapters import aws_resources


def test_dynamodb_resource_is_reused(monkeypatch) -> None:
    calls = []
    resource = object()
    boto3 = SimpleNamespace(resource=lambda service: calls.append(service) or resource)
    monkeypatch.setitem(__import__("sys").modules, "boto3", boto3)
    aws_resources.dynamodb_resource.cache_clear()

    try:
        assert aws_resources.dynamodb_resource() is resource
        assert aws_resources.dynamodb_resource() is resource
        assert calls == ["dynamodb"]
    finally:
        aws_resources.dynamodb_resource.cache_clear()
