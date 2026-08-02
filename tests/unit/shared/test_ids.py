"""Tests for shared identifier types and dependency boundaries."""

import ast
import shutil
import subprocess
from pathlib import Path

from apiguard.shared.errors import DomainError, IllegalStateTransitionError
from apiguard.shared.ids import (
    EvaluationResultId,
    EvidenceBundleId,
    ExecutionIntentId,
    OpenAPIContextSnapshotId,
    ValidationAttemptId,
    ValidationPlanId,
    VerificationTaskId,
)

PROJECT_ROOT = Path(__file__).parents[3]
SHARED_DIRECTORY = PROJECT_ROOT / "src" / "apiguard" / "shared"


def test_ids_compare_and_render_stably() -> None:
    assert VerificationTaskId("task-1") == VerificationTaskId("task-1")
    assert str(VerificationTaskId("task-1")) == "task-1"
    assert str(ValidationPlanId("plan-1")) == "plan-1"
    assert str(OpenAPIContextSnapshotId("snapshot-1")) == "snapshot-1"
    assert str(ValidationAttemptId("attempt-1")) == "attempt-1"
    assert str(ExecutionIntentId("intent-1")) == "intent-1"
    assert str(EvaluationResultId("evaluation-1")) == "evaluation-1"
    assert str(EvidenceBundleId("bundle-1")) == "bundle-1"


def test_pyright_rejects_mixing_identifier_types(tmp_path: Path) -> None:
    source_file = tmp_path / "invalid_identifier_assignment.py"
    source_file.write_text(
        "\n".join(
            [
                "from apiguard.shared.ids import ValidationPlanId, VerificationTaskId",
                "",
                "def accepts_plan(identifier: ValidationPlanId) -> None:",
                "    pass",
                "",
                "accepts_plan(VerificationTaskId('task-1'))",
            ]
        ),
        encoding="utf-8",
    )
    pyright = shutil.which("pyright")
    assert pyright is not None

    result = subprocess.run(
        [pyright, str(source_file)],
        capture_output=True,
        check=False,
        cwd=PROJECT_ROOT,
        encoding="utf-8",
    )

    assert result.returncode != 0
    assert "VerificationTaskId" in result.stdout
    assert "ValidationPlanId" in result.stdout


def test_errors_use_the_minimal_shared_hierarchy() -> None:
    assert issubclass(IllegalStateTransitionError, DomainError)


def test_shared_has_no_reverse_business_or_infrastructure_imports() -> None:
    forbidden_prefixes = (
        "apiguard.application",
        "apiguard.infrastructure",
        "apiguard.tasking",
        "apiguard.web",
    )

    for path in SHARED_DIRECTORY.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ] + [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]

        assert not any(
            module.startswith(forbidden_prefixes) for module in imported_modules
        )
