from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "title", "created_at", "read_at"]
    list_filter = ["category"]
    search_fields = ["user__name", "title"]
