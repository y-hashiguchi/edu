"""Sprint 9 — Alembic structural invariants for curriculum seed."""

import importlib.util
import pathlib
import uuid


def _load_migration():
    versions_dir = pathlib.Path(__file__).parent.parent / "alembic" / "versions"
    candidates = list(versions_dir.glob("*sprint9_curriculum_editing*.py"))
    assert len(candidates) == 1, f"expected 1 sprint9 migration, got {candidates}"
    spec = importlib.util.spec_from_file_location(
        "sprint9_migration", candidates[0]
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sprint9_migration_chains_from_sprint7_followup():
    m = _load_migration()
    assert m.down_revision == "a1b2c3d4e5f6"


def test_sprint9_migration_uses_fixed_uuids():
    m = _load_migration()
    assert m.AI_DRIVEN_DEV_UUID == uuid.UUID(
        "00000000-0000-4000-8000-000000000001"
    )
    assert m.AI_ERA_SE_UUID == uuid.UUID("00000000-0000-4000-8000-000000000002")


def test_sprint9_migration_seed_does_not_import_registry():
    """seed payload は COURSE_REGISTRY を import せず、dict literal で
    凍結されている (将来 registry を変更しても migration 挙動不変)。"""
    m = _load_migration()
    import inspect
    source = inspect.getsource(m)
    assert "from app.data.courses" not in source
    assert "COURSE_REGISTRY" not in source
