# HANDOVER — Sprint 28 ALB runbook + Terraform（2026-06-17）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 28 — 外部 ALB デプロイ手順 |
| 前提 | Sprint 27 完了 |

## 実装サマリ

| 変更 | 内容 |
|------|------|
| `docs/infra/alb-deploy.md` | ALB + EC2 Compose + RDS/ElastiCache/S3 構成 runbook |
| `infra/terraform/alb/` | 最小 Terraform（ALB, SG, TG, HTTPS ルーティング） |

アプリコード変更なし。502 passed ベースライン維持。

## 将来候補

- 既存 local ファイルの S3 移行スクリプト
- ECS/Fargate 向け Compose 代替
