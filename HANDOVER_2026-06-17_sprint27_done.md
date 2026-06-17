# HANDOVER — Sprint 27 S3 upload storage（2026-06-17）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 27 — 提出ファイル S3 バックエンド |
| 前提 | Sprint 26 完了 |

## 実装サマリ

| 変更 | 内容 |
|------|------|
| `UPLOAD_STORAGE_BACKEND` | `local`（既定）または `s3` |
| `file_storage_s3.py` | put/get/delete + `s3://bucket/key` URI |
| `stored_filename()` | local / S3 両対応の basename 取得 |
| `boto3` | backend 依存に追加 |

### 環境変数（S3 時）

```bash
UPLOAD_STORAGE_BACKEND=s3
S3_UPLOAD_BUCKET=your-bucket
S3_UPLOAD_PREFIX=uploads
S3_UPLOAD_REGION=ap-northeast-1
```

IAM role または標準 AWS credential chain を使用。

## テストベースライン（ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 502 passed, 1 skipped |

## 将来候補

- 外部 LB（ALB）向け Terraform / runbook
- 既存 local ファイルの S3 移行スクリプト
