"""Structural SQLAlchemy rows for the frozen first SQLite schema."""

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ID_TYPE = String(36)
UTC_TEXT_TYPE = String(27)

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """The sole declarative base and metadata source for migrations."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class VerificationTaskRow(Base):
    __tablename__ = "verification_tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type IN ('OPENAPI_CONTRACT', 'BUSINESS_RULE', 'STATE_FLOW')",
            name="task_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PREPARING', 'AWAITING_CONFIRMATION', 'READY', 'CANCELLED')",
            name="status",
        ),
        CheckConstraint(
            "non_production_confirmed IS NULL OR non_production_confirmed IN (0, 1)",
            name="non_production_confirmed_boolean",
        ),
        ForeignKeyConstraint(
            ["task_id", "current_confirmed_plan_id"],
            ["validation_plan_snapshots.task_id", "validation_plan_snapshots.plan_id"],
            name="fk_verification_tasks_current_confirmed_plan",
        ),
    )

    task_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_objective: Mapped[str] = mapped_column(Text, nullable=False)
    original_rule_text: Mapped[str | None] = mapped_column(Text)
    openapi_source_kind: Mapped[str | None] = mapped_column(String(64))
    openapi_source_value: Mapped[str | None] = mapped_column(Text)
    target_base_url: Mapped[str | None] = mapped_column(Text)
    non_production_confirmed: Mapped[int | None] = mapped_column()
    test_data_json: Mapped[str | None] = mapped_column(Text)
    allowed_operation_scope_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_confirmed_plan_id: Mapped[str | None] = mapped_column(ID_TYPE)
    last_preparation_error_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
    updated_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
    cancelled_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class OpenAPISnapshotRow(Base):
    __tablename__ = "openapi_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "version_no", name="uq_openapi_snapshots_task_version"
        ),
        UniqueConstraint(
            "task_id",
            "openapi_snapshot_id",
            name="uq_openapi_snapshots_task_snapshot",
        ),
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint("raw_size_bytes >= 0", name="raw_size_nonnegative"),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="content_sha256",
        ),
        Index("ix_openapi_snapshots_task_id", "task_id"),
        Index("ix_openapi_snapshots_content_sha256", "content_sha256"),
    )

    openapi_snapshot_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("verification_tasks.task_id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_display_value: Mapped[str] = mapped_column(Text, nullable=False)
    openapi_version: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_document: Mapped[str] = mapped_column(Text, nullable=False)
    raw_size_bytes: Mapped[int] = mapped_column(nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_context_json: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostics_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)


class ModelCallRecordRow(Base):
    __tablename__ = "model_call_records"
    __table_args__ = (
        UniqueConstraint(
            "preparation_run_id",
            "call_sequence",
            name="uq_model_call_records_run_sequence",
        ),
        CheckConstraint("call_sequence > 0", name="call_sequence_positive"),
        CheckConstraint(
            "call_kind IN ('PRIMARY', 'TRANSIENT_RETRY', 'FORMAT_REPAIR')",
            name="call_kind",
        ),
        Index("ix_model_call_records_task_id", "task_id"),
        Index("ix_model_call_records_preparation_run_id", "preparation_run_id"),
        Index("ix_model_call_records_openapi_snapshot_id", "openapi_snapshot_id"),
    )

    model_call_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("verification_tasks.task_id"), nullable=False
    )
    openapi_snapshot_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("openapi_snapshots.openapi_snapshot_id"), nullable=False
    )
    preparation_run_id: Mapped[str] = mapped_column(ID_TYPE, nullable=False)
    call_sequence: Mapped[int] = mapped_column(nullable=False)
    call_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    raw_output_text: Mapped[str | None] = mapped_column(Text)
    structured_output_json: Mapped[str | None] = mapped_column(Text)
    validation_errors_json: Mapped[str | None] = mapped_column(Text)
    provider_request_id: Mapped[str | None] = mapped_column(String(256))
    token_usage_json: Mapped[str | None] = mapped_column(Text)
    error_json: Mapped[str | None] = mapped_column(Text)


class NormalizedRuleRow(Base):
    __tablename__ = "normalized_rules"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "version_no",
            name="uq_normalized_rules_task_version",
        ),
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="content_sha256",
        ),
        Index("ix_normalized_rules_task_id", "task_id"),
        Index("ix_normalized_rules_openapi_snapshot_id", "openapi_snapshot_id"),
        Index("ix_normalized_rules_model_call_id", "model_call_id"),
    )

    normalized_rule_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("verification_tasks.task_id"), nullable=False
    )
    openapi_snapshot_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("openapi_snapshots.openapi_snapshot_id"), nullable=False
    )
    model_call_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("model_call_records.model_call_id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(nullable=False)
    original_rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_rule_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)


class ValidationPlanSnapshotRow(Base):
    __tablename__ = "validation_plan_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "version_no",
            name="uq_validation_plan_snapshots_task_version",
        ),
        UniqueConstraint(
            "task_id",
            "plan_id",
            name="uq_validation_plan_snapshots_task_plan",
        ),
        UniqueConstraint(
            "task_id",
            "plan_id",
            "openapi_snapshot_id",
            name="uq_validation_plan_snapshots_task_plan_snapshot",
        ),
        CheckConstraint("version_no > 0", name="version_positive"),
        CheckConstraint(
            "stage IN ('CANDIDATE', 'VALIDATED', 'CONFIRMED')", name="stage"
        ),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="content_sha256",
        ),
        Index("ix_validation_plan_snapshots_task_id", "task_id"),
        Index("ix_validation_plan_snapshots_stage", "stage"),
        Index("ix_validation_plan_snapshots_normalized_rule_id", "normalized_rule_id"),
        Index(
            "ix_validation_plan_snapshots_openapi_snapshot_id", "openapi_snapshot_id"
        ),
    )

    plan_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("verification_tasks.task_id"), nullable=False
    )
    normalized_rule_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("normalized_rules.normalized_rule_id"), nullable=False
    )
    openapi_snapshot_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("openapi_snapshots.openapi_snapshot_id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_issues_json: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    confirmation_json: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)


class ValidationAttemptRow(Base):
    __tablename__ = "validation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "attempt_no",
            name="uq_validation_attempts_task_attempt_no",
        ),
        UniqueConstraint(
            "task_id",
            "execution_intent_id",
            name="uq_validation_attempts_task_execution_intent",
        ),
        ForeignKeyConstraint(
            ["task_id", "plan_id", "openapi_snapshot_id"],
            [
                "validation_plan_snapshots.task_id",
                "validation_plan_snapshots.plan_id",
                "validation_plan_snapshots.openapi_snapshot_id",
            ],
            name="fk_validation_attempts_plan_snapshot",
        ),
        CheckConstraint("attempt_no > 0", name="attempt_no_positive"),
        CheckConstraint("actual_send_count BETWEEN 0 AND 3", name="actual_send_count"),
        CheckConstraint("status IN ('EXECUTING', 'COMPLETED')", name="status"),
        CheckConstraint(
            "conclusion IS NULL OR conclusion IN ('PASSED', 'SUSPECTED_DEFECT', 'INCONCLUSIVE', 'EXECUTION_FAILED')",
            name="conclusion",
        ),
        CheckConstraint("is_rerun IN (0, 1)", name="is_rerun_boolean"),
        Index(
            "uq_validation_attempt_one_executing_per_task",
            "task_id",
            unique=True,
            sqlite_where=text("status = 'EXECUTING'"),
        ),
    )

    attempt_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("verification_tasks.task_id"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(nullable=False)
    plan_id: Mapped[str] = mapped_column(ID_TYPE, nullable=False)
    openapi_snapshot_id: Mapped[str] = mapped_column(ID_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_intent_id: Mapped[str] = mapped_column(ID_TYPE, nullable=False)
    is_rerun: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )
    previous_attempt_id: Mapped[str | None] = mapped_column(
        ID_TYPE, ForeignKey("validation_attempts.attempt_id")
    )
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
    started_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    actual_send_count: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )
    evaluation_result_id: Mapped[str | None] = mapped_column(
        ID_TYPE, ForeignKey("evaluation_results.evaluation_result_id")
    )
    evidence_bundle_id: Mapped[str | None] = mapped_column(
        ID_TYPE, ForeignKey("evidence_bundles.evidence_bundle_id")
    )
    conclusion: Mapped[str | None] = mapped_column(String(32))


class StepExecutionRecordRow(Base):
    __tablename__ = "step_execution_records"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "step_index",
            name="uq_step_execution_records_attempt_step_index",
        ),
        UniqueConstraint(
            "attempt_id",
            "plan_step_id",
            name="uq_step_execution_records_attempt_plan_step",
        ),
        CheckConstraint("step_index > 0", name="step_index_positive"),
        CheckConstraint("send_count >= 0", name="send_count_nonnegative"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED')",
            name="status",
        ),
        Index("ix_step_execution_records_attempt_id", "attempt_id"),
        Index("ix_step_execution_records_status", "status"),
    )

    step_record_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("validation_attempts.attempt_id"), nullable=False
    )
    plan_step_id: Mapped[str] = mapped_column(ID_TYPE, nullable=False)
    step_index: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_input_json: Mapped[str | None] = mapped_column(Text)
    send_count: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )
    extracted_variables_json: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    completed_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    failure_reason_json: Mapped[str | None] = mapped_column(Text)
    skip_reason_json: Mapped[str | None] = mapped_column(Text)


class HttpSendRecordRow(Base):
    __tablename__ = "http_send_records"
    __table_args__ = (
        UniqueConstraint(
            "step_record_id",
            "send_no_in_step",
            name="uq_http_send_records_step_send_no",
        ),
        UniqueConstraint(
            "attempt_id",
            "global_send_no",
            name="uq_http_send_records_attempt_global_send_no",
        ),
        CheckConstraint("global_send_no > 0", name="global_send_no_positive"),
        CheckConstraint("send_no_in_step > 0", name="send_no_in_step_positive"),
        CheckConstraint(
            "request_body_size_bytes >= 0", name="request_body_size_nonnegative"
        ),
        CheckConstraint(
            "response_declared_size_bytes IS NULL OR response_declared_size_bytes >= 0",
            name="response_declared_size_nonnegative",
        ),
        CheckConstraint(
            "response_captured_size_bytes IS NULL OR response_captured_size_bytes >= 0",
            name="response_captured_size_nonnegative",
        ),
        CheckConstraint(
            "status IN ('DISPATCHED', 'RESPONDED', 'FAILED', 'UNKNOWN_AFTER_INTERRUPT')",
            name="status",
        ),
        CheckConstraint(
            "method IN ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE')", name="method"
        ),
        CheckConstraint("is_retry IN (0, 1)", name="is_retry_boolean"),
        CheckConstraint(
            "reached_service IS NULL OR reached_service IN (0, 1)",
            name="reached_service_boolean",
        ),
        CheckConstraint(
            "response_truncated IN (0, 1)", name="response_truncated_boolean"
        ),
        CheckConstraint(
            "response_body_sha256 IS NULL OR (length(response_body_sha256) = 64 AND response_body_sha256 NOT GLOB '*[^0-9a-f]*')",
            name="response_body_sha256",
        ),
    )

    send_record_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("validation_attempts.attempt_id"), nullable=False
    )
    step_record_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("step_execution_records.step_record_id"), nullable=False
    )
    global_send_no: Mapped[int] = mapped_column(nullable=False)
    send_no_in_step: Mapped[int] = mapped_column(nullable=False)
    is_retry: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )
    retry_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    sanitized_url: Mapped[str] = mapped_column(Text, nullable=False)
    query_params_json: Mapped[str] = mapped_column(Text, nullable=False)
    request_headers_json: Mapped[str] = mapped_column(Text, nullable=False)
    request_body: Mapped[str | None] = mapped_column(Text)
    request_body_size_bytes: Mapped[int] = mapped_column(nullable=False)
    dispatched_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(UTC_TEXT_TYPE)
    reached_service: Mapped[int | None] = mapped_column()
    response_status_code: Mapped[int | None] = mapped_column()
    response_headers_json: Mapped[str | None] = mapped_column(Text)
    response_body: Mapped[str | None] = mapped_column(Text)
    response_declared_size_bytes: Mapped[int | None] = mapped_column()
    response_captured_size_bytes: Mapped[int | None] = mapped_column()
    response_body_sha256: Mapped[str | None] = mapped_column(String(64))
    response_truncated: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
    )
    error_json: Mapped[str | None] = mapped_column(Text)


class EvaluationResultRow(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        CheckConstraint(
            "length(evaluation_input_sha256) = 64 AND evaluation_input_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="evaluation_input_sha256",
        ),
        CheckConstraint(
            "conclusion IN ('PASSED', 'SUSPECTED_DEFECT', 'INCONCLUSIVE', 'EXECUTION_FAILED')",
            name="conclusion",
        ),
        CheckConstraint(
            "required_steps_complete IN (0, 1)", name="required_steps_complete_boolean"
        ),
        CheckConstraint(
            "preconditions_proven IN (0, 1)", name="preconditions_proven_boolean"
        ),
        CheckConstraint(
            "critical_evidence_missing IN (0, 1)",
            name="critical_evidence_missing_boolean",
        ),
        CheckConstraint(
            "attribution_ambiguous IN (0, 1)", name="attribution_ambiguous_boolean"
        ),
        Index("ix_evaluation_results_conclusion", "conclusion"),
        Index("ix_evaluation_results_plan_id", "plan_id"),
        Index("ix_evaluation_results_created_at", "created_at"),
    )

    evaluation_result_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ID_TYPE,
        ForeignKey("validation_attempts.attempt_id"),
        nullable=False,
        unique=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("validation_plan_snapshots.plan_id"), nullable=False
    )
    openapi_snapshot_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("openapi_snapshots.openapi_snapshot_id"), nullable=False
    )
    evaluation_input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    assertions_json: Mapped[str] = mapped_column(Text, nullable=False)
    required_steps_complete: Mapped[int] = mapped_column(nullable=False)
    preconditions_proven: Mapped[int] = mapped_column(nullable=False)
    critical_evidence_missing: Mapped[int] = mapped_column(nullable=False)
    attribution_ambiguous: Mapped[int] = mapped_column(nullable=False)
    conclusion: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_code: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_detail_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)


class EvidenceBundleRow(Base):
    __tablename__ = "evidence_bundles"
    __table_args__ = (
        CheckConstraint(
            "length(manifest_sha256) = 64 AND manifest_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="manifest_sha256",
        ),
        Index("ix_evidence_bundles_task_id", "task_id"),
        Index("ix_evidence_bundles_plan_id", "plan_id"),
        Index("ix_evidence_bundles_sealed_at", "sealed_at"),
        Index("ix_evidence_bundles_manifest_sha256", "manifest_sha256"),
    )

    evidence_bundle_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ID_TYPE,
        ForeignKey("validation_attempts.attempt_id"),
        nullable=False,
        unique=True,
    )
    task_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("verification_tasks.task_id"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("validation_plan_snapshots.plan_id"), nullable=False
    )
    openapi_snapshot_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("openapi_snapshots.openapi_snapshot_id"), nullable=False
    )
    evaluation_result_id: Mapped[str] = mapped_column(
        ID_TYPE,
        ForeignKey("evaluation_results.evaluation_result_id"),
        nullable=False,
        unique=True,
    )
    bundle_format_version: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)


class DerivedReportRow(Base):
    __tablename__ = "derived_reports"
    __table_args__ = (
        UniqueConstraint(
            "evidence_bundle_id",
            "report_version",
            name="uq_derived_reports_bundle_version",
        ),
        CheckConstraint("report_version > 0", name="report_version_positive"),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="content_sha256",
        ),
        Index("ix_derived_reports_evidence_bundle_id", "evidence_bundle_id"),
        Index("ix_derived_reports_created_at", "created_at"),
    )

    report_id: Mapped[str] = mapped_column(ID_TYPE, primary_key=True)
    evidence_bundle_id: Mapped[str] = mapped_column(
        ID_TYPE, ForeignKey("evidence_bundles.evidence_bundle_id"), nullable=False
    )
    report_version: Mapped[int] = mapped_column(nullable=False)
    format: Mapped[str] = mapped_column(String(64), nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(UTC_TEXT_TYPE, nullable=False)
