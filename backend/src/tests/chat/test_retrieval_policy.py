from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.retrieval.retrieval_policy import allow_rag, allow_web


def test_allow_rag_requires_explicit_flag():
    assert allow_rag(CapabilityPolicy()) is False
    assert allow_rag(CapabilityPolicy(allow_rag=True)) is True


def test_allow_web_requires_explicit_flag():
    assert allow_web(CapabilityPolicy()) is False
    assert allow_web(CapabilityPolicy(allow_web=True)) is True
