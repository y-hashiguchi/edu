from app.config import asyncpg_connect_args, normalize_database_url


def test_render_postgres_url_uses_asyncpg_driver() -> None:
    assert (
        normalize_database_url("postgresql://user:secret@db.internal:5432/ai_tutor")
        == "postgresql+asyncpg://user:secret@db.internal:5432/ai_tutor"
    )


def test_asyncpg_database_url_is_unchanged() -> None:
    url = "postgresql+asyncpg://user:secret@db.internal:5432/ai_tutor"

    assert normalize_database_url(url) == url


def test_supabase_pooler_url_uses_asyncpg_driver() -> None:
    assert (
        normalize_database_url(
            "postgres://postgres.project:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
        )
        == "postgresql+asyncpg://postgres.project:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    )


def test_asyncpg_connect_args_generate_unique_prepared_statement_names() -> None:
    connect_args = asyncpg_connect_args()
    name_func = connect_args["prepared_statement_name_func"]

    first = name_func()
    second = name_func()

    assert first.startswith("__asyncpg_")
    assert first.endswith("__")
    assert first != second
