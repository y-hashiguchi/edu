# Claude Code 引き継ぎドキュメント
## AI駆動型開発 補足カリキュラム — AIチューターシステム

**作成日：** 2026-06-01  
**引き継ぎ元：** Claude（claude.ai チャット上でのデモ作成）  
**引き継ぎ先：** Claude Code（本格実装フェーズ）  
**プロジェクトオーナー：** yhashi84

---

## 1. このドキュメントの目的

claude.ai チャット上でインタラクティブデモ（HTML/JS Artifact）として作成した
「AI駆動型開発 補足カリキュラム AIチューター」を、
**FastAPI + Vue.js（LearnAIスタック）で本格実装する**ための引き継ぎ情報をまとめる。

---

## 2. 背景・経緯

### 2-1. 発端

ChatGPT が提案した「新人エンジニアにIBM Bobを学習させる最適な方法」をベースに、
実際に動くAIチューターシステムを構築することになった。

### 2-2. デモで確認したこと

claude.ai 上のArtifact（HTML + Claude API直呼び）として以下を実装・動作確認済み：

- 4フェーズのカリキュラム切り替えUI
- フェーズごとに異なるシステムプロンプトを持つAIチューター
- クイック質問ボタン（3問/フェーズ）
- テキスト入力によるフリーQ&A
- 会話履歴の保持（同一フェーズ内）

### 2-3. 対象カリキュラム（添付画像より）

タイトル：**AI駆動型開発 補足カリキュラム ロードマップ**  
対象者：訓練修了後メンバー（Java/Python基礎・HTML/CSS/JS・DB基礎・ソフトウェア設計の基本 修了済み）  
推奨期間：約3〜4ヶ月

---

## 3. カリキュラム定義（実装の核心）

以下の4フェーズが本システムの教育コンテンツ。
実装時はこのデータ構造をDBまたは設定ファイルで管理すること。

### Phase 1：開発環境の近代化（2〜3週間）

**ゴール：** AIツールを使いこなすための「土台」を固める

**学習スキル：**
- Git / GitHub
- VSCode拡張機能
- ターミナル操作
- REST API基礎

**課題：**
1. Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成
2. VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認
3. curlでREST APIを叩き、JSONレスポンス構造をまとめる

**AIチューター システムプロンプト：**
```
あなたはAI駆動型開発を教える教育AIチューターです。
対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。
現在のフェーズ：Phase1「開発環境の近代化」。
Git・VSCode・REST APIの基礎を教えます。
指導方針：
- 既存の知識（Java/Python）と紐付けて説明する
- 手を動かさせることを重視する
- 答えをすぐ教えず、まず考えさせる
- 3〜5文程度で日本語で返答する
```

---

### Phase 2：AIツール活用マスター（3〜4週間）

**ゴール：** 「AIと一緒にコードを書く」体験を積む

**学習スキル：**
- プロンプトエンジニアリング
- Cursor IDE
- GitHub Copilot
- Claude活用

**課題：**
1. Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録
2. 同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる
3. ClaudeにコードレビューさせてPDCA

**AIチューター システムプロンプト：**
```
あなたはAI駆動型開発を教える教育AIチューターです。
対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。
現在のフェーズ：Phase2「AIツール活用マスター」。
Cursor IDE・GitHub Copilot・Claudeの実践的な使い方を指導します。
指導方針：
- プロンプトの良し悪しを具体例で教える
- AIを鵜呑みにしない批判的思考を育てる
- 実際に手を動かさせる課題を出す
- 3〜5文程度で日本語で返答する
```

---

### Phase 3：AI協調型開発ワークフロー（AI補助コーディング期間）

**ゴール：** 実際の開発タスクにAIを組み込む

**学習スキル：**
- AIペアプログラミング
- AIによるコードレビュー
- テスト自動生成
- 仕様書からのコード生成

**課題：**
1. Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理
2. 仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘
3. AIとペアで新機能（検索機能など）を実装。会話ログも提出

**AIチューター システムプロンプト：**
```
あなたはAI駆動型開発を教える教育AIチューターです。
対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。
現在のフェーズ：Phase3「AI協調型開発ワークフロー」。
AIペアプログラミング・コードレビュー・テスト自動生成を教えます。
指導方針：
- AIの出力を検証する習慣をつけさせる
- 開発品質の観点（セキュリティ・テスト・可読性）を意識させる
- ソクラテス式で深く考えさせる
- 3〜5文程度で日本語で返答する
```

---

### Phase 4：AIアプリ開発実践（4〜6週間）

**ゴール：** 「AIを使う」から「AIを組み込む」へ

**学習スキル：**
- API連携（Claude / OpenAI）
- RAG基礎
- PythonでAIツール作成
- プロダクト設計

**課題：**
1. Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）
2. RAGデモ作成（Python + ChromaDB + Claude API）
3. 業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）

**AIチューター システムプロンプト：**
```
あなたはAI駆動型開発を教える教育AIチューターです。
対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。
現在のフェーズ：Phase4「AIアプリ開発実践」。
Claude/OpenAI API連携・RAG・PythonでのAIツール開発を教えます。
指導方針：
- 実装の具体的な手順をステップで示す
- RAGの概念をわかりやすく説明する
- 企画力・提案力も育てる
- 3〜5文程度で日本語で返答する
```

---

## 4. 本格実装の要件定義

### 4-1. 追加すべき機能（デモに存在しない）

| 機能 | 概要 | 優先度 |
|------|------|--------|
| ユーザー認証 | ログイン・受講者管理 | 高 |
| 進捗管理 | フェーズ達成状況をDB保存 | 高 |
| フェーズ解放ロック | 前フェーズ課題提出後に次解放 | 高 |
| 課題提出機能 | テキスト・ファイルアップロード | 中 |
| AI課題採点 | 提出物をAIが評価・コメント | 中 |
| 管理者ダッシュボード | 全受講者の進捗一覧 | 中 |
| 会話履歴永続化 | セッションをまたいで保持 | 低 |

### 4-2. 技術スタック（LearnAIと同一）

```
フロントエンド：  Vue.js 3 + Pinia + Vite
バックエンド：    FastAPI（Python）
DB：             PostgreSQL + pgvector
AI：             Anthropic Claude API（claude-sonnet-4-20250514）
インフラ：        Docker Compose（開発）/ AWS（本番）
認証：           JWT
```

### 4-3. DB設計（案）

```sql
-- 受講者テーブル
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 進捗管理テーブル
CREATE TABLE progress (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    phase        INTEGER NOT NULL,  -- 1〜4
    status       VARCHAR(20) DEFAULT 'locked',  -- locked / in_progress / submitted / completed
    started_at   TIMESTAMP,
    completed_at TIMESTAMP
);

-- 会話履歴テーブル
CREATE TABLE chat_history (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    phase      INTEGER NOT NULL,
    role       VARCHAR(10) NOT NULL,  -- user / assistant
    content    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 課題提出テーブル
CREATE TABLE submissions (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    phase        INTEGER NOT NULL,
    task_no      INTEGER NOT NULL,  -- 課題番号（1〜3）
    content      TEXT,
    file_path    VARCHAR(500),
    ai_feedback  TEXT,
    score        INTEGER,  -- 0〜100
    submitted_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. APIエンドポイント設計（案）

```
POST   /api/auth/login              # ログイン
GET    /api/users/me                # 自分の情報取得

GET    /api/progress                # 自分の進捗取得
PATCH  /api/progress/{phase}        # 進捗更新

GET    /api/curriculum/phases       # フェーズ一覧・課題内容取得

POST   /api/chat                    # AIチューターへメッセージ送信
GET    /api/chat/history/{phase}    # 会話履歴取得

POST   /api/submissions/{phase}     # 課題提出
GET    /api/submissions/{phase}     # 提出履歴取得

GET    /api/admin/dashboard         # 管理者：全員の進捗（要管理者権限）
```

---

## 6. フロントエンド画面構成（案）

```
/login                    # ログイン画面
/dashboard                # マイダッシュボード（進捗確認）
/curriculum               # カリキュラム一覧
/curriculum/:phase        # フェーズ詳細・課題確認
/curriculum/:phase/chat   # AIチューターチャット画面
/curriculum/:phase/submit # 課題提出画面
/admin                    # 管理者ダッシュボード（受講者管理）
```

---

## 7. AIチューターの実装方針

### 7-1. バックエンドでのClaude API呼び出し

セキュリティ上、APIキーはバックエンド管理。フロントから直接呼び出さない。

```python
# FastAPI エンドポイント例
@router.post("/api/chat")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    phase = request.phase
    user_message = request.message

    # 会話履歴をDBから取得
    history = await get_chat_history(current_user.id, phase)

    # システムプロンプトをフェーズごとに切り替え
    system_prompt = CURRICULUM[phase]["system_prompt"]

    # Claude API呼び出し
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=system_prompt,
        messages=history + [{"role": "user", "content": user_message}]
    )

    ai_reply = response.content[0].text

    # 会話履歴をDBに保存
    await save_chat_history(current_user.id, phase, "user", user_message)
    await save_chat_history(current_user.id, phase, "assistant", ai_reply)

    return {"reply": ai_reply}
```

### 7-2. フェーズ解放ロジック

```python
# Phase 1は最初から開放、2以降は前フェーズ完了で解放
def is_phase_unlocked(user_id: int, phase: int) -> bool:
    if phase == 1:
        return True
    prev_progress = get_progress(user_id, phase - 1)
    return prev_progress.status == "completed"
```

---

## 8. 実装の進め方（推奨順序）

```
Step 1: LearnAIリポジトリにブランチを切る
        例: git checkout -b feature/ai-tutor-curriculum

Step 2: DBマイグレーション（上記4テーブル）

Step 3: カリキュラムデータをPythonの定数ファイルで管理
        例: app/data/curriculum.py

Step 4: FastAPIでチャットエンドポイントを実装・動作確認

Step 5: Vue.jsで最低限のチャット画面を実装（フェーズ切り替え + メッセージ送受信）

Step 6: 進捗管理・フェーズロック機能を追加

Step 7: 課題提出・AI採点機能を追加

Step 8: 管理者ダッシュボードを実装
```

---

## 9. デモコード（参考）

### チャットUIのコアロジック（Vue.js）

```vue
<script setup>
import { ref, reactive } from 'vue'
import { useProgressStore } from '@/stores/progress'
import api from '@/lib/api'

const props = defineProps({ phase: Number })
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  inputText.value = ''
  messages.value.push({ role: 'user', content: text })
  isLoading.value = true

  try {
    const { data } = await api.post('/chat', { phase: props.phase, message: text })
    messages.value.push({ role: 'assistant', content: data.reply })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: 'エラーが発生しました。再試行してください。' })
  } finally {
    isLoading.value = false
  }
}
</script>
```

---

## 10. 関連リポジトリ・環境情報

| 項目 | 内容 |
|------|------|
| Bitbucket Workspace | `smartbind_dev` |
| 開発環境 | Mac mini（メイン）/ Windows 11 Pro / MacBook |
| VPN | Tailscale |
| IDE | Cursor + Claude Code |
| コンテナ | Rancher Desktop |
| LearnAIスタック | FastAPI / Vue.js 3 / PostgreSQL / pgvector / Docker Compose |

---

## 11. 次のClaudeCodeセッションへの指示

以下をそのままClaudeCodeのプロンプトとして使用できる：

```
このドキュメント（HANDOVER_ai_tutor_curriculum.md）を読んで、
LearnAIのリポジトリにAIチューターカリキュラム機能を実装してください。

まず以下から始めてください：
1. app/data/curriculum.py を作成し、4フェーズのカリキュラムデータを定義する
2. DBマイグレーションファイルを作成する（progress・chat_history・submissions テーブル）
3. app/api/chat.py にチャットエンドポイントを実装する

APIキーは環境変数 ANTHROPIC_API_KEY から取得してください。
使用モデルは claude-sonnet-4-20250514 です。
```

---

*このドキュメントはclaude.aiチャット上でのデモ作成セッションをもとに自動生成されました。*  
*実装時は要件変更に応じて随時更新してください。*
