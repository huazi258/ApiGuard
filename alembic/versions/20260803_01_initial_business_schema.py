"""Initial frozen SQLite business schema.

Revision ID: 20260803_01
Revises:
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sha256_check(column: str) -> str:
    return f"length({column}) = 64 AND {column} NOT GLOB '*[^0-9a-f]*'"


def upgrade() -> None:
    """Create all eleven frozen business tables and their indexes."""

    op.create_table(
        "verification_tasks",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("verification_objective", sa.Text(), nullable=False),
        sa.Column("original_rule_text", sa.Text()),
        sa.Column("openapi_source_kind", sa.String(64)),
        sa.Column("openapi_source_value", sa.Text()),
        sa.Column("target_base_url", sa.Text()),
        sa.Column("non_production_confirmed", sa.Integer()),
        sa.Column("test_data_json", sa.Text()),
        sa.Column("allowed_operation_scope_json", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_confirmed_plan_id", sa.String(36)),
        sa.Column("last_preparation_error_json", sa.Text()),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.Column("updated_at", sa.String(27), nullable=False),
        sa.Column("cancelled_at", sa.String(27)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.CheckConstraint(
            "task_type IN ('OPENAPI_CONTRACT', 'BUSINESS_RULE', 'STATE_FLOW')",
            name="ck_verification_tasks_task_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PREPARING', 'AWAITING_CONFIRMATION', 'READY', 'CANCELLED')",
            name="ck_verification_tasks_status",
        ),
        sa.CheckConstraint(
            "non_production_confirmed IS NULL OR non_production_confirmed IN (0, 1)",
            name="ck_verification_tasks_non_production_confirmed_boolean",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "current_confirmed_plan_id"],
            ["validation_plan_snapshots.task_id", "validation_plan_snapshots.plan_id"],
            name="fk_verification_tasks_current_confirmed_plan",
        ),
    )
    op.create_table(
        "openapi_snapshots",
        sa.Column("openapi_snapshot_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(64), nullable=False),
        sa.Column("source_display_value", sa.Text(), nullable=False),
        sa.Column("openapi_version", sa.String(32), nullable=False),
        sa.Column("raw_document", sa.Text(), nullable=False),
        sa.Column("raw_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("normalized_context_json", sa.Text(), nullable=False),
        sa.Column("diagnostics_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["verification_tasks.task_id"],
            name="fk_openapi_snapshots_task_id_verification_tasks",
        ),
        sa.UniqueConstraint(
            "task_id", "version_no", name="uq_openapi_snapshots_task_version"
        ),
        sa.UniqueConstraint(
            "task_id", "openapi_snapshot_id", name="uq_openapi_snapshots_task_snapshot"
        ),
        sa.CheckConstraint(
            "version_no > 0", name="ck_openapi_snapshots_version_positive"
        ),
        sa.CheckConstraint(
            "raw_size_bytes >= 0", name="ck_openapi_snapshots_raw_size_nonnegative"
        ),
        sa.CheckConstraint(
            _sha256_check("content_sha256"), name="ck_openapi_snapshots_content_sha256"
        ),
    )
    op.create_index("ix_openapi_snapshots_task_id", "openapi_snapshots", ["task_id"])
    op.create_index(
        "ix_openapi_snapshots_content_sha256", "openapi_snapshots", ["content_sha256"]
    )
    op.create_table(
        "model_call_records",
        sa.Column("model_call_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("openapi_snapshot_id", sa.String(36), nullable=False),
        sa.Column("preparation_run_id", sa.String(36), nullable=False),
        sa.Column("call_sequence", sa.Integer(), nullable=False),
        sa.Column("call_kind", sa.String(32), nullable=False),
        sa.Column("provider_name", sa.String(128), nullable=False),
        sa.Column("model_name", sa.String(256), nullable=False),
        sa.Column("prompt_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("started_at", sa.String(27), nullable=False),
        sa.Column("completed_at", sa.String(27)),
        sa.Column("raw_output_text", sa.Text()),
        sa.Column("structured_output_json", sa.Text()),
        sa.Column("validation_errors_json", sa.Text()),
        sa.Column("provider_request_id", sa.String(256)),
        sa.Column("token_usage_json", sa.Text()),
        sa.Column("error_json", sa.Text()),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["verification_tasks.task_id"],
            name="fk_model_call_records_task_id_verification_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["openapi_snapshot_id"],
            ["openapi_snapshots.openapi_snapshot_id"],
            name="fk_model_call_records_openapi_snapshot_id_openapi_snapshots",
        ),
        sa.UniqueConstraint(
            "preparation_run_id",
            "call_sequence",
            name="uq_model_call_records_run_sequence",
        ),
        sa.CheckConstraint(
            "call_sequence > 0", name="ck_model_call_records_call_sequence_positive"
        ),
        sa.CheckConstraint(
            "call_kind IN ('PRIMARY', 'TRANSIENT_RETRY', 'FORMAT_REPAIR')",
            name="ck_model_call_records_call_kind",
        ),
    )
    for column in ("task_id", "preparation_run_id", "openapi_snapshot_id"):
        op.create_index(
            f"ix_model_call_records_{column}", "model_call_records", [column]
        )
    op.create_table(
        "normalized_rules",
        sa.Column("normalized_rule_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("openapi_snapshot_id", sa.String(36), nullable=False),
        sa.Column("model_call_id", sa.String(36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("original_rule_text", sa.Text(), nullable=False),
        sa.Column("normalized_rule_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["verification_tasks.task_id"],
            name="fk_normalized_rules_task_id_verification_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["openapi_snapshot_id"],
            ["openapi_snapshots.openapi_snapshot_id"],
            name="fk_normalized_rules_openapi_snapshot_id_openapi_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["model_call_id"],
            ["model_call_records.model_call_id"],
            name="fk_normalized_rules_model_call_id_model_call_records",
        ),
        sa.UniqueConstraint(
            "task_id", "version_no", name="uq_normalized_rules_task_version"
        ),
        sa.CheckConstraint(
            "version_no > 0", name="ck_normalized_rules_version_positive"
        ),
        sa.CheckConstraint(
            _sha256_check("content_sha256"), name="ck_normalized_rules_content_sha256"
        ),
    )
    for column in ("task_id", "openapi_snapshot_id", "model_call_id"):
        op.create_index(f"ix_normalized_rules_{column}", "normalized_rules", [column])
    op.create_table(
        "validation_plan_snapshots",
        sa.Column("plan_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("normalized_rule_id", sa.String(36), nullable=False),
        sa.Column("openapi_snapshot_id", sa.String(36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("validation_issues_json", sa.Text()),
        sa.Column("validated_at", sa.String(27)),
        sa.Column("confirmation_json", sa.Text()),
        sa.Column("confirmed_at", sa.String(27)),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["verification_tasks.task_id"],
            name="fk_validation_plan_snapshots_task_id_verification_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_rule_id"],
            ["normalized_rules.normalized_rule_id"],
            name="fk_validation_plan_snapshots_normalized_rule_id_normalized_rules",
        ),
        sa.ForeignKeyConstraint(
            ["openapi_snapshot_id"],
            ["openapi_snapshots.openapi_snapshot_id"],
            name="fk_validation_plan_snapshots_openapi_snapshot_id_openapi_snapshots",
        ),
        sa.UniqueConstraint(
            "task_id", "version_no", name="uq_validation_plan_snapshots_task_version"
        ),
        sa.UniqueConstraint(
            "task_id", "plan_id", name="uq_validation_plan_snapshots_task_plan"
        ),
        sa.UniqueConstraint(
            "task_id",
            "plan_id",
            "openapi_snapshot_id",
            name="uq_validation_plan_snapshots_task_plan_snapshot",
        ),
        sa.CheckConstraint(
            "version_no > 0", name="ck_validation_plan_snapshots_version_positive"
        ),
        sa.CheckConstraint(
            "stage IN ('CANDIDATE', 'VALIDATED', 'CONFIRMED')",
            name="ck_validation_plan_snapshots_stage",
        ),
        sa.CheckConstraint(
            _sha256_check("content_sha256"),
            name="ck_validation_plan_snapshots_content_sha256",
        ),
    )
    for column in ("task_id", "stage", "normalized_rule_id", "openapi_snapshot_id"):
        op.create_index(
            f"ix_validation_plan_snapshots_{column}",
            "validation_plan_snapshots",
            [column],
        )
    op.create_table(
        "validation_attempts",
        sa.Column("attempt_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("openapi_snapshot_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("execution_intent_id", sa.String(36), nullable=False),
        sa.Column("is_rerun", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("previous_attempt_id", sa.String(36)),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.Column("started_at", sa.String(27), nullable=False),
        sa.Column("completed_at", sa.String(27)),
        sa.Column(
            "actual_send_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("evaluation_result_id", sa.String(36)),
        sa.Column("evidence_bundle_id", sa.String(36)),
        sa.Column("conclusion", sa.String(32)),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["verification_tasks.task_id"],
            name="fk_validation_attempts_task_id_verification_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["previous_attempt_id"],
            ["validation_attempts.attempt_id"],
            name="fk_validation_attempts_previous_attempt_id_validation_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_result_id"],
            ["evaluation_results.evaluation_result_id"],
            name="fk_validation_attempts_evaluation_result_id_evaluation_results",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_bundle_id"],
            ["evidence_bundles.evidence_bundle_id"],
            name="fk_validation_attempts_evidence_bundle_id_evidence_bundles",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "plan_id", "openapi_snapshot_id"],
            [
                "validation_plan_snapshots.task_id",
                "validation_plan_snapshots.plan_id",
                "validation_plan_snapshots.openapi_snapshot_id",
            ],
            name="fk_validation_attempts_plan_snapshot",
        ),
        sa.UniqueConstraint(
            "task_id", "attempt_no", name="uq_validation_attempts_task_attempt_no"
        ),
        sa.UniqueConstraint(
            "task_id",
            "execution_intent_id",
            name="uq_validation_attempts_task_execution_intent",
        ),
        sa.CheckConstraint(
            "attempt_no > 0", name="ck_validation_attempts_attempt_no_positive"
        ),
        sa.CheckConstraint(
            "actual_send_count BETWEEN 0 AND 3",
            name="ck_validation_attempts_actual_send_count",
        ),
        sa.CheckConstraint(
            "status IN ('EXECUTING', 'COMPLETED')", name="ck_validation_attempts_status"
        ),
        sa.CheckConstraint(
            "conclusion IS NULL OR conclusion IN ('PASSED', 'SUSPECTED_DEFECT', 'INCONCLUSIVE', 'EXECUTION_FAILED')",
            name="ck_validation_attempts_conclusion",
        ),
        sa.CheckConstraint(
            "is_rerun IN (0, 1)", name="ck_validation_attempts_is_rerun_boolean"
        ),
    )
    op.create_index(
        "uq_validation_attempt_one_executing_per_task",
        "validation_attempts",
        ["task_id"],
        unique=True,
        sqlite_where=sa.text("status = 'EXECUTING'"),
    )
    op.create_table(
        "step_execution_records",
        sa.Column("step_record_id", sa.String(36), primary_key=True),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("plan_step_id", sa.String(36), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("resolved_input_json", sa.Text()),
        sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_variables_json", sa.Text()),
        sa.Column("started_at", sa.String(27)),
        sa.Column("completed_at", sa.String(27)),
        sa.Column("failure_reason_json", sa.Text()),
        sa.Column("skip_reason_json", sa.Text()),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["validation_attempts.attempt_id"],
            name="fk_step_execution_records_attempt_id_validation_attempts",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "step_index",
            name="uq_step_execution_records_attempt_step_index",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "plan_step_id",
            name="uq_step_execution_records_attempt_plan_step",
        ),
        sa.CheckConstraint(
            "step_index > 0", name="ck_step_execution_records_step_index_positive"
        ),
        sa.CheckConstraint(
            "send_count >= 0", name="ck_step_execution_records_send_count_nonnegative"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED')",
            name="ck_step_execution_records_status",
        ),
    )
    op.create_index(
        "ix_step_execution_records_attempt_id", "step_execution_records", ["attempt_id"]
    )
    op.create_index(
        "ix_step_execution_records_status", "step_execution_records", ["status"]
    )
    op.create_table(
        "http_send_records",
        sa.Column("send_record_id", sa.String(36), primary_key=True),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("step_record_id", sa.String(36), nullable=False),
        sa.Column("global_send_no", sa.Integer(), nullable=False),
        sa.Column("send_no_in_step", sa.Integer(), nullable=False),
        sa.Column("is_retry", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_reason", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("sanitized_url", sa.Text(), nullable=False),
        sa.Column("query_params_json", sa.Text(), nullable=False),
        sa.Column("request_headers_json", sa.Text(), nullable=False),
        sa.Column("request_body", sa.Text()),
        sa.Column("request_body_size_bytes", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.String(27), nullable=False),
        sa.Column("completed_at", sa.String(27)),
        sa.Column("reached_service", sa.Integer()),
        sa.Column("response_status_code", sa.Integer()),
        sa.Column("response_headers_json", sa.Text()),
        sa.Column("response_body", sa.Text()),
        sa.Column("response_declared_size_bytes", sa.Integer()),
        sa.Column("response_captured_size_bytes", sa.Integer()),
        sa.Column("response_body_sha256", sa.String(64)),
        sa.Column(
            "response_truncated", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_json", sa.Text()),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["validation_attempts.attempt_id"],
            name="fk_http_send_records_attempt_id_validation_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["step_record_id"],
            ["step_execution_records.step_record_id"],
            name="fk_http_send_records_step_record_id_step_execution_records",
        ),
        sa.UniqueConstraint(
            "step_record_id",
            "send_no_in_step",
            name="uq_http_send_records_step_send_no",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "global_send_no",
            name="uq_http_send_records_attempt_global_send_no",
        ),
        sa.CheckConstraint(
            "global_send_no > 0", name="ck_http_send_records_global_send_no_positive"
        ),
        sa.CheckConstraint(
            "send_no_in_step > 0", name="ck_http_send_records_send_no_in_step_positive"
        ),
        sa.CheckConstraint(
            "request_body_size_bytes >= 0",
            name="ck_http_send_records_request_body_size_nonnegative",
        ),
        sa.CheckConstraint(
            "response_declared_size_bytes IS NULL OR response_declared_size_bytes >= 0",
            name="ck_http_send_records_response_declared_size_nonnegative",
        ),
        sa.CheckConstraint(
            "response_captured_size_bytes IS NULL OR response_captured_size_bytes >= 0",
            name="ck_http_send_records_response_captured_size_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('DISPATCHED', 'RESPONDED', 'FAILED', 'UNKNOWN_AFTER_INTERRUPT')",
            name="ck_http_send_records_status",
        ),
        sa.CheckConstraint(
            "method IN ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE')",
            name="ck_http_send_records_method",
        ),
        sa.CheckConstraint(
            "is_retry IN (0, 1)", name="ck_http_send_records_is_retry_boolean"
        ),
        sa.CheckConstraint(
            "reached_service IS NULL OR reached_service IN (0, 1)",
            name="ck_http_send_records_reached_service_boolean",
        ),
        sa.CheckConstraint(
            "response_truncated IN (0, 1)",
            name="ck_http_send_records_response_truncated_boolean",
        ),
        sa.CheckConstraint(
            "response_body_sha256 IS NULL OR (length(response_body_sha256) = 64 AND response_body_sha256 NOT GLOB '*[^0-9a-f]*')",
            name="ck_http_send_records_response_body_sha256",
        ),
    )
    op.create_table(
        "evaluation_results",
        sa.Column("evaluation_result_id", sa.String(36), primary_key=True),
        sa.Column("attempt_id", sa.String(36), nullable=False, unique=True),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("openapi_snapshot_id", sa.String(36), nullable=False),
        sa.Column("evaluation_input_sha256", sa.String(64), nullable=False),
        sa.Column("assertions_json", sa.Text(), nullable=False),
        sa.Column("required_steps_complete", sa.Integer(), nullable=False),
        sa.Column("preconditions_proven", sa.Integer(), nullable=False),
        sa.Column("critical_evidence_missing", sa.Integer(), nullable=False),
        sa.Column("attribution_ambiguous", sa.Integer(), nullable=False),
        sa.Column("conclusion", sa.String(32), nullable=False),
        sa.Column("decision_code", sa.String(128), nullable=False),
        sa.Column("decision_detail_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["validation_attempts.attempt_id"],
            name="fk_evaluation_results_attempt_id_validation_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["validation_plan_snapshots.plan_id"],
            name="fk_evaluation_results_plan_id_validation_plan_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["openapi_snapshot_id"],
            ["openapi_snapshots.openapi_snapshot_id"],
            name="fk_evaluation_results_openapi_snapshot_id_openapi_snapshots",
        ),
        sa.CheckConstraint(
            _sha256_check("evaluation_input_sha256"),
            name="ck_evaluation_results_evaluation_input_sha256",
        ),
        sa.CheckConstraint(
            "conclusion IN ('PASSED', 'SUSPECTED_DEFECT', 'INCONCLUSIVE', 'EXECUTION_FAILED')",
            name="ck_evaluation_results_conclusion",
        ),
        sa.CheckConstraint(
            "required_steps_complete IN (0, 1)",
            name="ck_evaluation_results_required_steps_complete_boolean",
        ),
        sa.CheckConstraint(
            "preconditions_proven IN (0, 1)",
            name="ck_evaluation_results_preconditions_proven_boolean",
        ),
        sa.CheckConstraint(
            "critical_evidence_missing IN (0, 1)",
            name="ck_evaluation_results_critical_evidence_missing_boolean",
        ),
        sa.CheckConstraint(
            "attribution_ambiguous IN (0, 1)",
            name="ck_evaluation_results_attribution_ambiguous_boolean",
        ),
    )
    for column in ("conclusion", "plan_id", "created_at"):
        op.create_index(
            f"ix_evaluation_results_{column}", "evaluation_results", [column]
        )
    op.create_table(
        "evidence_bundles",
        sa.Column("evidence_bundle_id", sa.String(36), primary_key=True),
        sa.Column("attempt_id", sa.String(36), nullable=False, unique=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("openapi_snapshot_id", sa.String(36), nullable=False),
        sa.Column("evaluation_result_id", sa.String(36), nullable=False, unique=True),
        sa.Column("bundle_format_version", sa.String(64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("sealed_at", sa.String(27), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["validation_attempts.attempt_id"],
            name="fk_evidence_bundles_attempt_id_validation_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["verification_tasks.task_id"],
            name="fk_evidence_bundles_task_id_verification_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["validation_plan_snapshots.plan_id"],
            name="fk_evidence_bundles_plan_id_validation_plan_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["openapi_snapshot_id"],
            ["openapi_snapshots.openapi_snapshot_id"],
            name="fk_evidence_bundles_openapi_snapshot_id_openapi_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_result_id"],
            ["evaluation_results.evaluation_result_id"],
            name="fk_evidence_bundles_evaluation_result_id_evaluation_results",
        ),
        sa.CheckConstraint(
            _sha256_check("manifest_sha256"), name="ck_evidence_bundles_manifest_sha256"
        ),
    )
    for column in ("task_id", "plan_id", "sealed_at", "manifest_sha256"):
        op.create_index(f"ix_evidence_bundles_{column}", "evidence_bundles", [column])
    op.create_table(
        "derived_reports",
        sa.Column("report_id", sa.String(36), primary_key=True),
        sa.Column("evidence_bundle_id", sa.String(36), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(64), nullable=False),
        sa.Column("renderer_version", sa.String(128), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_bundle_id"],
            ["evidence_bundles.evidence_bundle_id"],
            name="fk_derived_reports_evidence_bundle_id_evidence_bundles",
        ),
        sa.UniqueConstraint(
            "evidence_bundle_id",
            "report_version",
            name="uq_derived_reports_bundle_version",
        ),
        sa.CheckConstraint(
            "report_version > 0", name="ck_derived_reports_report_version_positive"
        ),
        sa.CheckConstraint(
            _sha256_check("content_sha256"), name="ck_derived_reports_content_sha256"
        ),
    )
    op.create_index(
        "ix_derived_reports_evidence_bundle_id",
        "derived_reports",
        ["evidence_bundle_id"],
    )
    op.create_index("ix_derived_reports_created_at", "derived_reports", ["created_at"])


def downgrade() -> None:
    """Drop the first business schema in dependency-safe reverse order."""

    op.drop_index("ix_derived_reports_created_at", table_name="derived_reports")
    op.drop_index("ix_derived_reports_evidence_bundle_id", table_name="derived_reports")
    op.drop_table("derived_reports")
    for column in ("task_id", "plan_id", "sealed_at", "manifest_sha256"):
        op.drop_index(f"ix_evidence_bundles_{column}", table_name="evidence_bundles")
    op.drop_table("evidence_bundles")
    for column in ("conclusion", "plan_id", "created_at"):
        op.drop_index(
            f"ix_evaluation_results_{column}", table_name="evaluation_results"
        )
    op.drop_table("evaluation_results")
    op.drop_table("http_send_records")
    op.drop_index(
        "ix_step_execution_records_status", table_name="step_execution_records"
    )
    op.drop_index(
        "ix_step_execution_records_attempt_id", table_name="step_execution_records"
    )
    op.drop_table("step_execution_records")
    op.drop_index(
        "uq_validation_attempt_one_executing_per_task", table_name="validation_attempts"
    )
    op.drop_table("validation_attempts")
    for column in ("task_id", "stage", "normalized_rule_id", "openapi_snapshot_id"):
        op.drop_index(
            f"ix_validation_plan_snapshots_{column}",
            table_name="validation_plan_snapshots",
        )
    op.drop_table("validation_plan_snapshots")
    for column in ("task_id", "openapi_snapshot_id", "model_call_id"):
        op.drop_index(f"ix_normalized_rules_{column}", table_name="normalized_rules")
    op.drop_table("normalized_rules")
    for column in ("task_id", "preparation_run_id", "openapi_snapshot_id"):
        op.drop_index(
            f"ix_model_call_records_{column}", table_name="model_call_records"
        )
    op.drop_table("model_call_records")
    op.drop_index("ix_openapi_snapshots_content_sha256", table_name="openapi_snapshots")
    op.drop_index("ix_openapi_snapshots_task_id", table_name="openapi_snapshots")
    op.drop_table("openapi_snapshots")
    op.drop_table("verification_tasks")
