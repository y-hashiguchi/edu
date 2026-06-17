# HANDOVER — Sprint 25 CI embedding stub（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 25 — CI HuggingFace 429 対策 |
| 前提 | Sprint 24 完了 |

## 背景

CI で fastembed が HuggingFace からモデル DL する際、429 で embedding 系テストが一括 fail することがあった（Sprint 22 初回 CI）。pytest / GitHub Actions では外部 DL を避ける。

## 実装サマリ

| 変更 | 内容 |
|------|------|
| `EMBEDDING_STUB_MODE` | config + `.env.example` |
| `embedding_stub.py` | SHA-256 ベースの決定論的 384-dim ベクトル |
| `EmbeddingClient` | stub mode 時は fastembed をスキップ |
| `conftest.py` | デフォルト `EMBEDDING_STUB_MODE=true` |
| `ci.yml` | backend / e2e job に明示設定 |
| `test_embedding_client` | 意味的類似度テストは `@pytest.mark.integration` で skip |

本番・ローカル RAG 検証: `EMBEDDING_STUB_MODE=false` で従来どおり fastembed を使用。

## テストベースライン（ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 498 passed, 1 skipped |

## 将来候補

- TLS / 外部 LB / マネージド DB への production-deploy 拡張
