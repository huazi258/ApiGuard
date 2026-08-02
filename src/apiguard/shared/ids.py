"""Nominal identifier types shared by later domain entities."""

from typing import NewType

VerificationTaskId = NewType("VerificationTaskId", str)
ValidationPlanId = NewType("ValidationPlanId", str)
OpenAPIContextSnapshotId = NewType("OpenAPIContextSnapshotId", str)
ValidationAttemptId = NewType("ValidationAttemptId", str)
ExecutionIntentId = NewType("ExecutionIntentId", str)
EvaluationResultId = NewType("EvaluationResultId", str)
EvidenceBundleId = NewType("EvidenceBundleId", str)
