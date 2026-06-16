# HANDOVER — Sprint 22 ai-era-se 全シラバス運用（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| 最新 HEAD | `e11235a` |
| スプリント | Sprint 22 — ai-era-se catalog / docs 同期 |
| 前提 | Sprint 21 完了 |
| GitHub Actions | **success** — [#27629342997](https://github.com/y-hashiguchi/edu/actions/runs/27629342997) |

## 背景

Phase 2-4 の課題定義は Sprint 7 LOW-1 + Sprint 9 migration で **コード・DB 投入済み**。
残タスクは登録フォーム catalog の説明文と README が「Phase 1 パイロット」のままだった点の解消。

## 実装サマリ

| 変更 | 内容 |
|------|------|
| Migration | `courses.description` を全 4 フェーズ・31 課題の説明に UPDATE |
| `ai_era_se.py` | `CourseData.description` を DB と同文案に統一 |
| Tests | catalog description / registry description の整合 |
| README | マルチコース運用の ai-era-se 表記を更新 |

### ai-era-se 構成（確定）

| Phase | 課題数 | テーマ |
|-------|--------|--------|
| 1 | 8 | 土台づくり（第1〜8週） |
| 2 | 10 | 実践力の習得（第9〜20週） |
| 3 | 8 | AI活用・協働（第21〜36週） |
| 4 | 5 | 自律・発信（第37〜48週） |

## ローカル適用

```bash
cd backend && uv run alembic upgrade head
```

## 将来候補

- TLS / 外部 LB / マネージド DB への production-deploy 拡張
