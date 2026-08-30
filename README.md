# 勤怠管理・外注請求システム

正社員の勤怠・休暇管理と、外注（業務委託）先の稼働管理から請求書・支払調書発行までを
一元化する Web アプリケーション。契約ごとに専用のクラウド環境へリリースする。

## ドキュメント

| 資料 | 内容 |
|---|---|
| [設計書](https://claude.ai/code/artifact/a967d776-6094-4142-986d-0f5baf76efff) | 技術選定、アーキテクチャ、業務ロジック、API、画面、非機能 |
| [ER図・スキーマ定義](https://claude.ai/code/artifact/3492cd1a-c46e-4053-9d3b-dab3d7e9add2) | 全33テーブルのER図とカラム定義 |
| [マルチテナント設計（追補）](https://claude.ai/code/artifact/bceefeeb-f36f-4b6e-8a20-734d851ed276) | 環境分離、ドメイン設計、環境の生成・更新・運用 |

## 構成

```
backend/    Django 5 + DRF（Python 3.12）
frontend/   Vue 3 + TypeScript + Vite + Pinia + PrimeVue
infra/      Terraform モジュール（契約ごとの環境を生成）
docs/       ADR
```

## 開発の始め方

### Docker を使う場合

前提: Docker Desktop、Node.js 22、Python 3.12。

```bash
cp .env.example .env

make up          # PostgreSQL と Django を起動
make migrate     # マイグレーションを作成して適用
make seed        # 会社設定と勤務体系の初期データ
make superuser   # 管理者アカウントを作成

cd frontend && npm install && npm run dev
```

### Docker を使わずローカルで動かす場合

前提: Homebrew、PostgreSQL 16（`brew install postgresql@16`）、Python 3.12+、Node.js 22。
WeasyPrint（請求書PDF）は `cairo` `pango` `gdk-pixbuf` `harfbuzz` が必要
（`brew install cairo pango gdk-pixbuf harfbuzz`）。

`scripts/local-dev.sh` が PostgreSQL・Django・Vite の起動と停止をまとめて面倒を見る
（初回は venv 作成・`.env` 生成・`npm install`・migrate・`seed_initial_data` まで自動で行う）。

```bash
scripts/local-dev.sh up          # まとめて起動
scripts/local-dev.sh status      # 起動状況を確認
scripts/local-dev.sh logs        # Django のログを追う（vite / postgres も指定可）
scripts/local-dev.sh seed-demo   # 社員・外注先・打刻履歴・休暇申請のデモデータを投入（任意・初回のみでよい）
scripts/local-dev.sh down        # まとめて停止
```

このスクリプトが起動していない Vite（別ターミナルで手動起動したもの等）は `down` で
止めない。PID は `.local/run/`、ログは `.local/log/` に置く（いずれも Git 管理対象外）。

`seed-demo` を実行すると、以下でログインできる（`make superuser` の代わり）。

| 区分 | メール | パスワード |
|---|---|---|
| 管理者 | admin@example.com | admin12345678 |
| 正社員 | sato@example.com（他 suzuki / takahashi / tanaka / watanabe / ito） | employee12345 |

- フロント: http://localhost:5173
- API ドキュメント: http://localhost:8000/api/docs/
- 管理サイト: http://localhost:8000/admin/（マスタ管理は主にここで行う。会社設定・勤務体系・
  休暇種類・有給ポリシー・36協定ポリシー・祝日カレンダー・監査ログ・税制マスタ）

有給の自動付与バッチ（本番は毎日02:00に実行）を手動で試すには
`python3 manage.py grant_paid_leave` を実行する。出勤率8割未満のユーザーには自動付与しない
（設計方針どおり、`create_demo_data` は付与ロットを直接投入しているため通常は再実行不要）。

### API の型をフロントへ反映する

```bash
make schema   # OpenAPI から src/types/api.d.ts を生成
```

バックエンドのシリアライザを変えたら必ず実行する。CI でスキーマ差分を検出する。

## 設計上の約束

実装を進めるうえで守るべき方針。破ると後から直すのが高くつく。

1. **労務・税務の計算はビューにも ORM にも書かない。** `apps/*/services/` の純関数に置き、
   ビューとバッチの両方から呼ぶ。テストはこの層に集中させる。
2. **金額はすべて `Decimal`。** `float` を経由させない。
3. **打刻は1分単位でそのまま保存する。** 日単位の切り捨ては賃金全額払いの原則に反する。
4. **法令で決まる値は管理画面から編集させない。** 税率・源泉徴収率・免税事業者の控除率・
   国民の祝日はデータマイグレーションでコードに含め、デプロイで全環境に配る。
5. **会社が決めるルールはすべてマスタにする。** 所定労働時間、休憩方式、有給の付与日数。
   設計時に値を決め打ちしない。
6. **月次承認でロックした期間の打刻は変更できない。** アプリ層のガードと DB トリガの二重で守る。
7. **カラムの削除・リネームは2リリースに分ける。** 段階デプロイでバージョンが並走するため。

## 実装フェーズ

| Phase | 内容 | 状態 |
|---|---|---|
| 0 | 基盤（認証・会社設定・勤務体系・CI・Terraform） | ローカル実装済み（Terraform/CIは未着手） |
| 1 | 勤怠（打刻・日次月次集計・修正申請・承認） | ローカル実装済み |
| 2 | 休暇（休暇種類・有給の付与消化失効・管理簿） | ローカル実装済み（管理簿PDF出力含む） |
| 3 | アラート（有給5日・36協定・通知） | ローカル実装済み（バッチはAPI内で都度計算。定期実行は未設定） |
| 4 | 外注（マスタ・単価履歴・稼働入力・締め） | ローカル実装済み |
| 5 | 請求・帳票（請求書・PDF・送信・支払調書・CSV） | ローカル実装済み（メールはコンソール送信、CSVエクスポートは未実装） |
| 6 | 初期データ・導入設定ウィザード・環境台帳 | 初期データ投入コマンドのみ（ウィザードは未実装） |
| 7 | 総合テスト・受入 | バックエンド196件・フロント31件（結合）＋5件（E2E, Playwright）で主要フローを検証済み |

ローカル動作の前提として、契約ごとの環境分離・Terraform・GCP/AWS・SESは対象外。
メール送信はDjangoのコンソールバックエンドで代替している。PDFはDjangoのストレージ抽象化
（`STORAGES["default"]`）を経由しているため、ローカルはファイルシステム、本番はS3等の
Cloud Storageバックエンドに設定を差し替えるだけで対応できる。

## テストの実行方法

```bash
# backend/ 配下、venv有効化後
python -m pytest              # 単体・結合試験（services層の純関数〜APIエンドポイントまで）
ruff check .                  # Lint

# frontend/ 配下
npm test                      # 単体・画面結合試験（vitest、jsdom + モックAPI）
npm run build                 # 型検査（vue-tsc）+ ビルド
npx playwright install chromium  # 初回のみ: E2E用ブラウザを取得
npm run test:e2e              # E2E試験（Playwright、実ブラウザ + 実バックエンド）
```

E2E試験は `scripts/local-dev.sh up` で起動済みのバックエンド・フロントエンド・PostgreSQLに
対して実行する（未起動なら `playwright.config.ts` の `webServer` が自動起動する）。
`create_demo_data` コマンドで投入したデモアカウントを使って実際にログインするため、
デモデータが入っていることが前提。読み取り専用の操作のみで完結するよう作られており、
テスト実行によってデータが変化することはない。
