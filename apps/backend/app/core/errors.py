"""Core exception hierarchy alias for TalkFlow control plane."""

from app.packages.contracts.errors import TalkFlowError

AppError = TalkFlowError

__all__ = ["AppError", "TalkFlowError"]
