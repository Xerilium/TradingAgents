"""Azure endpoint and deployment selection without network requests."""

import pytest

from tradingagents.llm_clients.azure_client import AzureOpenAIClient

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def azure_environment(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-azure-key")
    monkeypatch.setenv("OPENAI_API_VERSION", "2025-03-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://environment.openai.azure.com/")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT_NAME", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_AD_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)


def test_explicit_endpoint_overrides_environment():
    llm = AzureOpenAIClient(
        "test-deployment", base_url="https://configured.openai.azure.com/"
    ).get_llm()

    assert llm.azure_endpoint == "https://configured.openai.azure.com/"
    assert llm.openai_api_base is None
    assert str(llm.root_client.base_url) == (
        "https://configured.openai.azure.com/openai/deployments/test-deployment/"
    )


@pytest.mark.parametrize("base_url", [None, ""])
def test_unset_endpoint_uses_environment(base_url):
    llm = AzureOpenAIClient("test-deployment", base_url=base_url).get_llm()

    assert llm.azure_endpoint == "https://environment.openai.azure.com/"
    assert str(llm.root_client.base_url) == (
        "https://environment.openai.azure.com/openai/deployments/test-deployment/"
    )


@pytest.mark.parametrize("deployment", [None, "environment-deployment"])
def test_deployment_environment_overrides_model(monkeypatch, deployment):
    if deployment is not None:
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", deployment)

    llm = AzureOpenAIClient(
        "configured-model", base_url="https://configured.openai.azure.com/"
    ).get_llm()

    selected = deployment or "configured-model"
    assert llm.model_name == "configured-model"
    assert llm.deployment_name == selected
    assert str(llm.root_client.base_url) == (
        f"https://configured.openai.azure.com/openai/deployments/{selected}/"
    )
