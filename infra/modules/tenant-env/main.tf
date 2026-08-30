# 契約1件分のクラウド環境。
#
# 実装は Phase 0 後半。ここでは構成の骨格と、実装時に守るべき点をコメントで残す。

terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

locals {
  project_id      = "kintai-${var.tenant_code}"
  fallback_domain = "${var.tenant_code}.${var.service_domain}"
  labels = {
    tenant  = var.tenant_code
    managed = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Stage 1: 顧客待ちなしで作れる範囲
# ---------------------------------------------------------------------------
# - google_project                       課金アカウントに紐づけ、費用の按分をプロジェクト単位にする
# - google_project_service               必要なAPIの有効化
# - google_sql_database_instance         availability_type は var.enable_ha で切り替える
#                                        deletion_protection は必ず true
#                                        backup_configuration に PITR を有効化
# - google_storage_bucket                versioning と retention_policy を有効化（電子帳簿保存法）
# - google_secret_manager_secret         DB認証情報・SESキー
# - google_cloud_run_v2_service          全環境で同じ app_image。差は環境変数だけ
# - google_cloud_run_v2_job              日次・月次バッチ
# - google_cloud_scheduler_job           バッチの起動
# - google_compute_global_address        ロードバランサの静的IP。顧客に伝えるAレコードの値
# - google_certificate_manager_certificate  併設サブドメイン用（自社ドメインなので即発行できる）
# - google_compute_url_map / target_https_proxy / global_forwarding_rule
# - google_monitoring_alert_policy       通知先は共通。本文に tenant_code を必ず含める
# - google_billing_budget                原価の異常増を請求前に検知する

# ---------------------------------------------------------------------------
# Stage 2: 顧客の DNS 設定後
# ---------------------------------------------------------------------------
# - google_certificate_manager_dns_authorization  独自ドメイン用。
#     Search Console の所有権確認ではなく DNS 認可を使う。認可レコードは永続的なので、
#     顧客が一度設定すれば以後の証明書更新は自動で通る。
# - google_certificate_manager_certificate        独自ドメイン用
# - google_certificate_manager_certificate_map    SNI で2ドメインを1つのLBに載せる
#
# count = var.stage >= 2 ? 1 : 0 で切り替える。
