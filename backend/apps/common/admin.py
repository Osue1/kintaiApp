from django.contrib import admin

from .models import IdempotencyKey


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "key", "user", "response_status", "created_at")
    list_filter = ("endpoint",)
    search_fields = ("key",)
