output "project_id" {
  description = "この契約のGCPプロジェクトID"
  value       = local.project_id
}

output "fallback_url" {
  description = "併設サブドメイン。DNS設定を待たずに引き渡せる"
  value       = "https://${var.tenant_code}.${var.service_domain}"
}

output "custom_url" {
  description = "顧客の独自ドメイン（Stage 2 完了後に有効）"
  value       = "https://${var.custom_domain}"
}

output "dns_a_record" {
  description = "顧客に依頼する A レコードの値"
  value = {
    type = "A"
    name = var.custom_domain
    # value = google_compute_global_address.default.address
    value = "（Stage 1 適用後に確定）"
  }
}

output "dns_authorization_record" {
  description = "顧客に依頼する DNS 認可用 CNAME。証明書の自動更新に永続的に必要"
  value = {
    type = "CNAME"
    name = "_acme-challenge.${var.custom_domain}"
    # value = google_certificate_manager_dns_authorization.custom.dns_resource_record[0].data
    value = "（Stage 1 適用後に確定）"
  }
}
