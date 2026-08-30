variable "tenant_code" {
  description = "契約企業を識別する短い英小文字。プロジェクトIDと併設サブドメインに使う"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.tenant_code))
    error_message = "英小文字で始まる2〜21文字（英小文字・数字・ハイフン）にしてください。"
  }
}

variable "display_name" {
  description = "契約企業の表示名"
  type        = string
}

variable "custom_domain" {
  description = "顧客の独自ドメイン。apex は不可（コーポレートサイトと衝突するため）"
  type        = string
  validation {
    condition     = length(split(".", var.custom_domain)) >= 3
    error_message = "サブドメインを指定してください（例 kintai.acme.co.jp）。apex は使えません。"
  }
}

variable "service_domain" {
  description = "自社ドメイン。併設サブドメイン <tenant_code>.<service_domain> を張る"
  type        = string
  default     = "kintai-svc.jp"
}

variable "region" {
  description = "リージョン。国内保管要件のため既定は東京"
  type        = string
  default     = "asia-northeast1"
}

variable "db_tier" {
  description = "Cloud SQL のマシンタイプ"
  type        = string
  default     = "db-g1-small"
}

variable "enable_ha" {
  description = "Cloud SQL の HA 構成。上位プランのオプション。原価が月5,000円ほど増える"
  type        = bool
  default     = false
}

variable "admin_email" {
  description = "初回ログイン招待を送る管理者のメールアドレス"
  type        = string
}

variable "stage" {
  description = "1 = 顧客待ちなしで作れる範囲 / 2 = 独自ドメインの付与"
  type        = number
  default     = 1
  validation {
    condition     = contains([1, 2], var.stage)
    error_message = "stage は 1 か 2 を指定してください。"
  }
}

variable "app_image" {
  description = "デプロイするコンテナイメージ"
  type        = string
}
