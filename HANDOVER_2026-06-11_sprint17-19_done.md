# HANDOVER — Sprint 17–19 Phase / embeddings / catalog（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| 最新 HEAD | `b6d0246`（本体）+ E2E / docs 追記コミット予定 |
| Sprint 17–19 本体 | `b6d0246` |
| GitHub Actions | **success** — [#27609794017](https://github.com/y-hashiguchi/edu/actions/runs/27609794017) |
| スプリント | Sprint 17 Phase 追加・削除 / Sprint 18 embeddings 自動生成 / Sprint 19 catalog UI |
| 前提 | Sprint 16（Course 追加・削除）完了 |

## テストベースライン（CI / ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 487 passed |
| frontend vitest | 106 passed |
| Playwright E2E | 11 passed（Phase add/delete E2E 追記後） |

## 実装サマリ

### Sprint 17 — Phase 追加・削除

| 操作 | API | 仕様 |
|------|-----|------|
| 追加 | `POST /api/admin/curriculum/{slug}/phases` | 末尾に 1 phase + 1 task scaffold。progress backfill |
| 削除 | `DELETE /api/admin/curriculum/{slug}/phases/{phase_no}` | 最後の 1 phase は 409。submission ありは 409。番号リマップ |

**Migration:** `20260616_d4e5f6a7b8c9_sprint17_submission_phase_check.py` — `submissions.phase` CHECK を `phase >= 1` に緩和

**主要ファイル:**
- `backend/app/services/curriculum_edit.py` — `add_phase`, `delete_phase`, `_remap_phase_numbers`
- `backend/app/api/admin/curriculum.py` — phase create / delete routes
- `frontend/src/views/admin/AdminCurriculumEditView.vue` — 「+ Phase」ボタン
- `frontend/src/components/admin/CurriculumPhaseEditor.vue` — Phase 削除ボタン

### Sprint 18 — embeddings 自動生成

- `backend/app/services/curriculum_embeddings.py` — DB/cache ベース `seed_course_embeddings`
- Course 作成・Phase 追加後に API から自動 seed（テストは monkeypatch で noop）
- Course 削除時に embeddings も削除（`curriculum_course.delete_course`）
- `backend/scripts/seed_embeddings.py` — 全 Course 対応に更新

### Sprint 19 — catalog UI

- `frontend/src/views/LoginView.vue` — 登録時コース選択で `description` を表示
- `frontend/src/__tests__/LoginView.spec.ts` — description 表示テスト

### Tests（ローカル）

| スイート | 追加・更新 |
|----------|------------|
| `test_curriculum_edit_service.py` | phase add/delete |
| `test_admin_curriculum_api.py` | phase API |
| `test_curriculum_embeddings.py` | 新規 |
| `admin-curriculum.spec.ts` | Phase add/delete E2E + `deletePhase5IfPresent` ヘルパー |

## コミット履歴

```
b6d0246 feat(sprint-17-19): phase add/delete, auto embeddings, catalog descriptions
e96dcd5 docs(handover): sync local-dev-ready and README for Sprint 16 closure
1ad1ad0 docs(handover): record Sprint 16 CI green at f2c6a29
```

## 未実施（次セッション）

- [ ] publish 時の embeddings 差分再生成（Sprint 9 設計メモ参照）
- [ ] Phase 並び替え（Task move API と同様）

## 将来候補

- ai-era-se コンテンツ拡充
- TLS / 外部 LB / マネージド DB への production-deploy 拡張
