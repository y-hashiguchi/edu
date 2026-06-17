"""Sprint 7 — Alembic structural invariants.

We don't run alembic in pytest. This loads the migration module and
asserts fixed UUIDs, down_revision linkage, and presence of upgrade/
downgrade. The actual upgrade is exercised manually against the dev
DB and validated by data probes."""

import importlib.util
import pathlib
import uuid


def _load_migration():
    versions_dir = pathlib.Path(__file__).parent.parent / "alembic" / "versions"
    candidates = list(versions_dir.glob("*sprint7_multi_course*.py"))
    assert len(candidates) == 1, f"expected 1 sprint7 migration, got {candidates}"
    spec = importlib.util.spec_from_file_location("sprint7_migration", candidates[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sprint7_migration_uses_fixed_uuids():
    m = _load_migration()
    assert m.AI_DRIVEN_DEV_UUID == uuid.UUID("00000000-0000-4000-8000-000000000001")
    assert m.AI_ERA_SE_UUID == uuid.UUID("00000000-0000-4000-8000-000000000002")


def test_sprint7_migration_chains_from_sprint6():
    m = _load_migration()
    assert m.down_revision == "57242832bf0f"


def test_sprint7_migration_has_upgrade_and_downgrade():
    m = _load_migration()
    assert callable(m.upgrade)
    assert callable(m.downgrade)
