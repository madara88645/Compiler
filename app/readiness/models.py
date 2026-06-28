from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReadinessVerdict = Literal["ready", "clarify", "risky", "noise"]
SignalKind = Literal["unverifiable_reference", "vagueness", "risk", "noise"]


class ReadinessSignal(BaseModel):
    kind: SignalKind
    message: str


class ReadinessReport(BaseModel):
    verdict: ReadinessVerdict
    signals: list[ReadinessSignal] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
