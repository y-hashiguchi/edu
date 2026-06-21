# 管理者（admin）運用ガイド

AI チューター学習プラットフォーム（edu）の**管理者向け**操作ガイドです。受講者管理・提出物確認・通知配信・カリキュラム編集・コホート集計の各画面の使い方をまとめます。

- **対象:** 管理者権限を持つ運用担当者
- **関連:** 受講者向けは [new-engineer-demo-guide.md](./new-engineer-demo-guide.md)、インフラ運用は [../infra/render-demo-operations.md](../infra/render-demo-operations.md)

> ℹ️ **検証状況:** 本ガイドはコードベース（ルート定義・画面・API）に基づいて記述しています。admin 画面は管理者権限が必要なため、受講者フロー（登録・チャット・提出採点）のような公開デモでの live 実走検証は本ガイドの範囲では未実施です。画面ラベルや手順は実装に合わせていますが、初回運用時は実環境での確認を推奨します。

---

## 1. 前提: 管理者権限の付与

管理者画面（`/admin/*`）は **`is_admin` を持つユーザーのみ**アクセスできます。通常登録したユーザーを管理者に昇格するには、バックエンドの **Render Shell**（`edu-demo-api`）で次を実行します。

```bash
uv run python -m scripts.promote_admin admin@example.com
```

> 昇格はサーバー側スクリプトでのみ可能で、画面からは行えません（権限昇格の経路を1本に限定するため）。

---

## 2. 管理画面へのアクセス

1. 管理者アカウントで通常どおりログインします。
2. ブラウザで `/admin` を開きます（`/admin` は `/admin/users` にリダイレクト）。
3. 非管理者が `/admin/*` にアクセスするとコース一覧へ戻されます（ルートガードで保護）。

| 画面 | パス | 役割 |
|---|---|---|
| 受講者一覧 | `/admin/users` | 受講者の検索・一覧 |
| 受講者詳細 | `/admin/users/:id` | 進捗・ダッシュボード・コース追加 |
| 提出物詳細 | `/admin/submissions/:id` | 提出本文・AI採点・コメント |
| 通知作成 | `/admin/notify` | お知らせの作成・予約・履歴 |
| カリキュラム一覧 | `/admin/curriculum` | コース別カリキュラム編集の入口 |
| カリキュラム編集 | `/admin/curriculum/:courseSlug` | フェーズ・課題の編集／公開 |
| コホート集計 | `/admin/cohort` | 受講状況の集計ダッシュボード |

---

## 3. 受講者管理

### 3-1. 受講者一覧（`/admin/users`）
- **「受講者一覧」**画面で登録ユーザーを一覧・検索できます。
- 各行から受講者詳細へ遷移します。

### 3-2. 受講者詳細・進捗（`/admin/users/:id`）
- 受講者の **「フェーズ進捗」** と **「受講者のダッシュボード」**（弱点・推奨・進捗サマリ）を確認できます。
- **「コース追加」** から、その受講者を別コースに受講登録（enrollment）できます。

### 3-3. コホート（バッチ）設定
- 受講者のコース受講に**コホートラベル**（入講バッチ等）を付与できます。コホート集計（§7）での絞り込みに使われます。

**関連 API（運用/開発者向け）:**
| 操作 | メソッド・パス |
|---|---|
| 受講者一覧 | `GET /api/admin/users` |
| 受講者詳細 | `GET /api/admin/users/{user_id}` |
| ダッシュボード | `GET /api/admin/users/{user_id}/dashboard` |
| コース追加（enroll） | `POST /api/admin/users/{user_id}/enrollments` |
| コホート更新 | `PATCH /api/admin/users/{user_id}/enrollments/{course_slug}` |

---

## 4. 提出物の確認とフィードバック

### 提出物詳細（`/admin/submissions/:id`）
受講者の課題提出を確認します。表示項目:
- **「提出本文」** — 受講者が記入した内容
- **「添付ファイル」** — アップロードされたファイル（ダウンロード可）
- **「AI フィードバック」** — AI（Claude）による採点コメントとスコア
- **「採点履歴」** — 再採点を含む採点の履歴

運用操作:
- **コメント**を付けて受講者へフィードバックできます（スレッド形式）。
- 必要に応じて**再採点**を実行できます（短時間の連続再採点はクールダウンで制限）。

**関連 API:**
| 操作 | メソッド・パス |
|---|---|
| 提出一覧 | `GET /api/admin/submissions` |
| 提出詳細 | `GET /api/admin/submissions/{submission_id}` |
| コメント投稿 | `POST /api/admin/submissions/{submission_id}/comments`（系） |

---

## 5. 通知・お知らせの配信（`/admin/notify`）

「通知作成」画面でお知らせを配信します。

1. **宛先**を選びます（全体 / コース単位）。コース宛なら対象コースを指定。
2. **タイトル**と**本文**を入力します。
3. **即時送信**、または**予約送信**（日時指定）を選びます。
4. 送信後は **「予約一覧（pending）」** で予約済みを、**「最近送った通知」** で送信履歴を確認できます。

> ⚠️ **デモ環境では予約 broadcast worker が無効**（`SCHEDULED_BROADCAST_CRON_ENABLED=false`）です。**予約送信は登録できても、自動配信は実行されません。**デモでは即時送信を使ってください。予約配信を使うには worker 有効化が必要です（[../infra/render-demo-operations.md](../infra/render-demo-operations.md) §7 参照）。

**関連 API:**
| 操作 | メソッド・パス |
|---|---|
| 通知配信 | `POST /api/admin/notifications`（系） |
| 予約一覧 | `GET /api/admin/notifications/scheduled` |
| 予約取消 | `DELETE /api/admin/notifications/scheduled/{id}` |
| 送信履歴 | `GET /api/admin/notifications` |

---

## 6. カリキュラム編集

### 6-1. 一覧（`/admin/curriculum`）
**「カリキュラム編集」**画面で、編集対象のコースを選びます。

### 6-2. 編集（`/admin/curriculum/:courseSlug`）
- フェーズ・課題（タイトル・説明・システムプロンプト等）を編集できます。
- 連続入力時は**デバウンス自動保存**（下書き）が走ります（`admin_curriculum_write_rate_limit` で保護）。
- 編集内容を確定するには**公開（publish）**します。公開はカリキュラムキャッシュの再構築を伴うため、レート制限が厳しめ（`admin_curriculum_publish_rate_limit`）です。

> ⚠️ **デモは単一インスタンス**のため、`CURRICULUM_CACHE_PUBSUB_ENABLED=false`。公開後のキャッシュ反映は当該インスタンス内で完結します。複数インスタンス運用では pub/sub（Redis）有効化が必要です。

**関連 API:**
| 操作 | メソッド・パス |
|---|---|
| コース一覧 | `GET /api/admin/curriculum/` |
| コース詳細 | `GET /api/admin/curriculum/{course_slug}` |
| 作成 | `POST /api/admin/curriculum`（系） |
| 更新（フェーズ/課題） | `PUT /api/admin/curriculum/...` |
| 追加/削除 | `POST` / `DELETE /api/admin/curriculum/...` |
| 公開 | `POST /api/admin/curriculum/.../publish`（系） |

---

## 7. コホート集計ダッシュボード（`/admin/cohort`）

**「コホート集計」**画面で受講状況を俯瞰します。

- **集計サマリ** — コホート（バッチ）単位の進捗・受講状況。
- **「stuck 受講者」** — 一定日数アクティビティのない受講者（`COHORT_STUCK_INACTIVE_DAYS`、既定 7 日）。フォロー対象の把握に。
- **「skill tag ヒートマップ」** — スキルタグ別の弱点傾向の可視化。

**関連 API:**
| 操作 | メソッド・パス |
|---|---|
| コホート集計（系） | `GET /api/admin/courses/...` |

---

## 8. 運用上の注意

- 管理者の**書き込み操作**にはレート制限があります（`admin_write_rate_limit` 既定 60/分、カリキュラム書き込み 120/分・公開 10/分）。スクリプトで一括操作する際は上限に注意。
- 権限昇格は `promote_admin`（サーバー側）のみ。退任時は権限の見直しを。
- デモ環境固有の無効機能（予約 broadcast・カリキュラム pub/sub）は §5 / §6 の注記参照。

---

## 付録: admin API エンドポイント早見表

| 領域 | プレフィックス |
|---|---|
| 受講者・enrollment | `/api/admin/users` |
| 受講者ダッシュボード | `/api/admin/users/{id}/dashboard` |
| 提出物 | `/api/admin/submissions` |
| 提出コメント | `/api/admin/submissions`（コメント系） |
| 通知 | `/api/admin/notifications` |
| カリキュラム | `/api/admin/curriculum` |
| コホート集計 | `/api/admin/courses` |

> いずれも管理者トークン（`is_admin`）が必要です。`Authorization: Bearer <admin token>` を付与してください。
