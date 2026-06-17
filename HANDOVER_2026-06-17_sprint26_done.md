# HANDOVER — Sprint 26 production-deploy 拡張（2026-06-17）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 26 — TLS / マネージド DB / API スケール |
| 前提 | Sprint 25 完了 |

## 実装サマリ

| 変更 | 内容 |
|------|------|
| `docker-compose.prod.yml` | `postgres`/`redis` を `bundled-db` profile 化、`depends_on.required: false` |
| `docker-compose.prod.tls.yml` | Caddy 443/80、frontend/backend は内部のみ |
| `infra/caddy/Caddyfile` | APP_DOMAIN → SPA、API_DOMAIN → FastAPI |
| `Makefile` | `prod-tls`, `prod-managed`, `prod-tls-managed` |
| `docs/infra/production-deploy.md` | パターン別手順、migration head 更新 |

### デプロイコマンド

```bash
make prod              # bundled Postgres/Redis
make prod-tls          # + Let's Encrypt
make prod-managed      # 外部 DATABASE_URL / REDIS_URL
make prod-tls-managed  # TLS + マネージド DB
# スケール例
docker compose -f docker-compose.prod.yml -f docker-compose.prod.tls.yml \
  --profile bundled-db up -d --scale backend=3
```

## テストベースライン

インフラのみ変更。backend **498 passed, 1 skipped**（変更なし）。

## 将来候補

- upload を S3 等オブジェクトストレージへ移行（multi-host スケール時）
- 外部 LB（ALB）向け Terraform / _RUNBOOK 追加
