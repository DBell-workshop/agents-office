<p align="center">
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README.md">English</a> ·
  <a href="README_ja.md">日本語</a>
</p>

<p align="center">
  <img src="docs/demo.gif" width="800" alt="AgentsOffice Demo" />
</p>

<h1 align="center">AgentsOffice</h1>

<p align="center">
  <strong>あなたの AI チームに、目に見えるオフィスを</strong>
</p>

<p align="center">
  <a href="https://github.com/DBell-workshop/agents-office/stargazers"><img src="https://img.shields.io/github/stars/DBell-workshop/agents-office?style=social" alt="Stars" /></a>
  <a href="https://github.com/DBell-workshop/agents-office/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-BSL_1.1-blue" alt="License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-green" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/frontend-React%20%2B%20Phaser3-purple" alt="Frontend" /></a>
</p>

<p align="center">
  <a href="#use-cases">活用シーン</a> ·
  <a href="#features">機能</a> ·
  <a href="#quick-start">クイックスタート</a> ·
  <a href="#architecture">アーキテクチャ</a> ·
  <a href="#support">サポート</a> ·
  <a href="LICENSE">License</a>
</p>

---

## What is AgentsOffice?

AgentsOffice は**マルチ Agent 協調ワークベンチ**です。ドット絵風 RPG オフィスの中で、あなたの AI チームが「目に見える形で働く」姿を実現します。

役割を定義し、プロンプトを書き、スキルを装備するだけ。わずか 5 分で、あなただけの AI デジタル社員チームを立ち上げられます。

> **他の「ドット絵オフィス」プロジェクトとの違い：うちの Agent はただ歩き回るだけのキャラクターではありません。本当に仕事をします。**

| 他のプロジェクト | AgentsOffice |
|---------|-------------|
| 純粋な可視化ダッシュボード、Agent の状態表示のみ | **フル機能の AI ワークベンチ**、Agent が実際のスキルを持つ |
| 動かすには外部 AI ツールとの連携が必要 | **LLM 対話 + Skill エンジン内蔵**、すぐに使える |
| 単一ロールの表示のみ | **マルチロール協調**、ディスパッチャーが自動でタスクを振り分け |
| 見るだけ | **チャット・スキル発動・データ分析が可能** |

---

<a id="use-cases"></a>
## Use Cases - 業種を問わず、役割を定義すればそれがあなたのチーム

> 以下は実際の活用シーンです。どれも 5 分で設定できます。

### 📝 コンテンツ制作ワークショップ
> 一人で運営しているメディア？ コンテンツチームを付けましょう。

**企画プランナー** がトレンドからネタを発掘 + **編集者** が初稿の執筆・推敲 + **タイトル職人** が 10 個のタイトル案を生成。毎日オフィスを開いて、書きたい方向をグループチャットに投げるだけ。3 人の AI 社員が自動で分担し、あなたは最終判断だけすれば OK。

### 🎯 プロダクトデザインチーム
> リサーチ、競合分析、PRD――もう「人力パイプライン」は卒業。

**ユーザーリサーチャー** がフィードバックを整理しニーズを抽出 + **競合アナリスト** が競合の機能と戦略を分解 + **PRD アシスタント** が要件定義書を自動生成。分析結果は自動的に次の工程へ。コピペは不要です。

### 📚 学習サポートステーション
> 生徒に AI 教師チームを。

**ナレッジ解説員** が分かりやすい言葉で概念を説明 + **問題作成コーチ** がレベルに合わせた練習問題を出題 + **学習プランナー** が間違えた問題に基づいて復習計画を調整。ドット絵教室の AI 先生が、学びの体験をぐっと楽しくします。

### 🎧 カスタマーサポート研修センター
> 新人研修に、先輩社員の手を借りる必要なし。

**模擬カスタマー** がさまざまな購入者を演じ + **品質管理スーパーバイザー** が回答をリアルタイムで評価・採点 + **トークコーチ** が毎回の対話に改善アドバイス。トレーニング → 評価 → 改善のサイクルが 24 時間 365 日いつでも回ります。

### 💡 スタートアップ・ブレイントラスト
> コンサル会社を雇う予算がない？ AI 顧問チームを。

**マーケットアナリスト** が業界トレンドを調査 + **ビジネスアドバイザー** が収益化パスを整理 + **グロースエキスパート** が集客戦略を設計。ビジネスプランをグループチャットに投げれば、3 人の顧問が異なる視点からフィードバック。月額コストはランチ数回分程度。

### 💻 個人開発者ワークスペース
> コーディング以外のタスクは、AI 同僚に任せよう。

**プロダクトアシスタント** が要件整理とユーザーストーリー作成 + **コードレビュアー** がコードをレビューしバグを発見 + **運用ライター** がリリースノートやプロモーション文を作成。あなたはコードに集中し、残りはチームに任せましょう。

---

| シーン | コアバリュー | Agent 数 |
|------|---------|-----------|
| コンテンツ制作 | 一人で三人分の生産性 | 3 |
| プロダクトデザイン | リサーチからドキュメントまで自動連携 | 3 |
| 学習サポート | AI 教師チーム | 3 |
| カスタマーサポート研修 | トレーニング・評価・改善サイクル | 3 |
| スタートアップ知恵袋 | 手頃な価格のコンサルチーム | 3 |
| 個人開発 | 技術以外を全方位カバー | 3 |

**自分だけの活用シーンが思い浮かびましたか？** AgentsOffice を開いて Agent を作成し、プロンプトを書けば、すぐに稼働開始です。

---

<a id="features"></a>
## Features

### 🏢 ドット絵風 RPG オフィス
Phaser 3 ゲームエンジンで構築された 2D ドット絵オフィス。各 Agent には専用のデスク、部屋、アニメーションがあります。Agent をクリックすれば、すぐに会話を始められます。

### 🤖 柔軟な Agent システム
- **無制限**: Agent をいくつでも自由に作成し、理想のチームを構築
- **UI から設定**: 役割名、プロンプト、モデル、スキルをコードなしで変更可能
- **20 種のプリセットキャラクター**から選択可能。各 Agent に固有の見た目を

### 💬 インテリジェントな対話
- **グループチャット**: ディスパッチャーが意図を自動認識し、最適な Agent に振り分け
- **プライベートチャット**: 特定の Agent と 1 対 1 で深い対話が可能
- **Skill 自動トリガー**: Agent がスキルの必要性を検知すると自動実行

### 🔌 Skill プラグインシステム
- `BaseSkill` を継承するだけでカスタムスキルを開発可能
- 複数ステップのインタラクションに対応 (検索 → 選択 → 分析)
- SSE による実行進捗のリアルタイム配信

### 🗄️ データ管理
- データエンジニア Agent が CSV アップロード、テーブル作成、データクエリをサポート
- PostgreSQL による永続化、JSONB の柔軟なフィールド
- 外部データベースへの接続にも対応

### 🧮 コストトラッキング
- LLM 呼び出しごとに Token 使用量と費用を自動記録
- Agent 別・モデル別でコストレポートを閲覧
- 主要モデルの料金表を内蔵 (OpenAI、Claude、Gemini、DeepSeek)

---

<a id="quick-start"></a>
## Quick Start

### ワンクリック起動（推奨）

[Docker](https://www.docker.com/products/docker-desktop/) をインストールするだけで OK：

```bash
git clone https://github.com/DBell-workshop/agents-office.git
cd agents-office
cp .env.example .env   # .env を編集し、LLM API Key を1つ以上入力
docker compose up -d
```

**http://localhost:8001/static/office/** を開けばすぐ使えます。

### 開発モード

コードを変更したい場合（ホットリロード対応）：

```bash
# データベース
docker compose up postgres -d

# バックエンド
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# フロントエンド（別のターミナル）
cd frontend && npm install && npm run dev
```

開発モード: **http://localhost:5174/static/office/**

---

<a id="architecture"></a>
## Architecture

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  Phaser RPG Engine + React Overlay + ChatBox │
│  (ドット絵オフィス + Agentパネル + チャット)      │
└────────────────────┬────────────────────────┘
                     │ SSE / REST
┌────────────────────▼────────────────────────┐
│              FastAPI Backend                  │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ AgentChat │  │  Skills  │  │  Data     │  │
│  │ (振分/私聊)│  │  Engine  │  │  Manager  │  │
│  └─────┬────┘  └─────┬────┘  └─────┬─────┘  │
│        │             │             │         │
│  ┌─────▼─────────────▼─────────────▼──────┐  │
│  │           Service Layer                 │  │
│  │  LLM Service / Agent Runner             │  │
│  │  Skill Engine / Cost Tracker            │  │
│  └─────────────────┬──────────────────────┘  │
│                    │                         │
│  ┌─────────────────▼──────────────────────┐  │
│  │         PostgreSQL + SQLAlchemy         │  │
│  │    Agents / Skills / Tasks / Costs      │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

**Tech Stack:**
- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic
- **Frontend**: TypeScript, React, Phaser 3 (RPG engine)
- **AI**: LLM via OpenAI-compatible API (GPT, Claude, Gemini, Qwen, DeepSeek)
- **Database**: PostgreSQL with JSONB
- **Infra**: Docker Compose

---

<a id="support"></a>
## このプロジェクトを支援する

AgentsOffice はコミュニティ主導のオープンソースプロジェクトです。お役に立てたなら、ぜひご支援ください：

<p align="center">

**⭐ [Star をつける](https://github.com/DBell-workshop/agents-office)** — 最もシンプルな応援方法

**☕ [Buy Me a Coffee](https://buymeacoffee.com/)** — コーヒーをおごる

**💖 [GitHub Sponsors](https://github.com/sponsors/DBell-workshop)** — 長期スポンサーになる

**🎁 [Ko-fi](https://ko-fi.com/)** — ワンタイム寄付

</p>

> すべての Star とスポンサーシップが開発の原動力です！

---

## Roadmap

- [x] ドット絵風 RPG オフィス UI
- [x] Agent 動的設定 (UI パネル)
- [x] グループチャット振り分け & プライベートチャット
- [x] Skill プラグインエンジン
- [x] データエンジニア (ファイルアップロード、テーブル作成、SQL クエリ)
- [x] LLM コストトラッキング
- [ ] プリセット Skill テンプレートの拡充
- [ ] Agent 状態アニメーション (作業中 → キーボード入力、待機中 → コーヒーブレイク)
- [ ] モバイル対応
- [ ] Token チャージ & 使用量管理
- [ ] Skill マーケット (コミュニティ共有)

---

## Community

コミュニティに参加して、アイデアを共有したり、質問したり、Agent の設定を見せ合いましょう：

<p align="center">
  <a href="https://discord.gg/3Cpe5H6m"><img src="https://img.shields.io/badge/Discord-Join%20Server-5865F2?logo=discord&logoColor=white" alt="Discord" /></a>
</p>

<p align="center">
  <strong>WeChat グループ</strong>（QR をスキャンして参加。7日間有効、期限切れ後は Discussions で最新 QR を取得）<br/>
  <img src="docs/wechat-qr.jpg" width="200" alt="WeChat Group QR" />
</p>

---

## Contributing

コントリビューション大歓迎です！

- Issue でバグ報告や機能提案をお寄せください
- PR でコードの貢献をお待ちしています
- カスタム Skill を開発してコミュニティで共有しましょう
- [Discussions](https://github.com/DBell-workshop/agents-office/discussions) でアイデアを交換しましょう

---

## License

本プロジェクトは [Business Source License 1.1](LICENSE) を採用しています。

- ✅ 個人利用、学習、研究、社内評価は自由です
- ❌ 許可なく商用利用することはできません
- 📅 2030 年に自動的に Apache 2.0 オープンソースへ移行します

詳細は [LICENSE](LICENSE) ファイルをご覧ください。

---

<p align="center">
  <sub>Built with ❤️ by the AgentsOffice Team</sub>
</p>
