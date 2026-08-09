"""Versioned evaluation primitives for the teacher Agent."""

from .dataset import AgentEvalCase, EvalDataset, load_eval_dataset
from .evaluators import EvalResult, EvalSummary, evaluate_case, summarize_results

__all__ = [
    "AgentEvalCase",
    "EvalDataset",
    "EvalResult",
    "EvalSummary",
    "evaluate_case",
    "load_eval_dataset",
    "summarize_results",
]
