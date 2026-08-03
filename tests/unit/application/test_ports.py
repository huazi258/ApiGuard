"""Application ports remain independent from persistence infrastructure."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from apiguard.application.ports import DerivedReportRecord, EvidenceBundleRecord
from apiguard.shared.ids import (
    DerivedReportId,
    EvaluationResultId,
    EvidenceBundleId,
    OpenAPIContextSnapshotId,
    ValidationAttemptId,
    ValidationPlanId,
    VerificationTaskId,
)


def test_ports_do_not_import_persistence_frameworks_or_rows() -> None:
    source = Path("src/apiguard/application/ports.py").read_text(encoding="utf-8")

    assert "sqlalchemy" not in source
    assert "from apiguard.infrastructure" not in source
    assert "from fastapi" not in source
    assert "Row" not in source


def test_evidence_append_records_are_immutable() -> None:
    bundle = EvidenceBundleRecord(
        evidence_bundle_id=EvidenceBundleId(str(uuid4())),
        attempt_id=ValidationAttemptId(str(uuid4())),
        task_id=VerificationTaskId(str(uuid4())),
        plan_id=ValidationPlanId(str(uuid4())),
        openapi_snapshot_id=OpenAPIContextSnapshotId(str(uuid4())),
        evaluation_result_id=EvaluationResultId(str(uuid4())),
        bundle_format_version="v1",
        manifest_json="{}",
        manifest_sha256="a" * 64,
        sealed_at=datetime(2026, 8, 3, tzinfo=UTC),
    )
    report = DerivedReportRecord(
        report_id=DerivedReportId(str(uuid4())),
        evidence_bundle_id=bundle.evidence_bundle_id,
        report_version=1,
        format="html",
        renderer_version="v1",
        content_text="report",
        content_sha256="b" * 64,
        created_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    with pytest.raises(FrozenInstanceError):
        bundle.manifest_json = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.content_text = "changed"  # type: ignore[misc]
