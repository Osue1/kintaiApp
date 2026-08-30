from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification

DEFAULT_HISTORY_DAYS = 30
MAX_HISTORY_DAYS = 365


def _serialize(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "category": n.category,
        "title": n.title,
        "detail": n.body,
        "created_at": n.created_at.isoformat(),
        "read": n.read_at is not None,
    }


class NotificationListView(APIView):
    """マイページ通知の一覧。`days` を指定すると、その日数さかのぼった範囲の履歴を返す
    （未指定時はダッシュボード用に直近20件のみ）。"""

    @extend_schema(summary="通知一覧")
    def get(self, request: Request) -> Response:
        days_param = request.query_params.get("days")
        qs = Notification.objects.filter(user=request.user)

        if days_param is None:
            items = qs[:20]
        else:
            try:
                days = max(1, min(MAX_HISTORY_DAYS, int(days_param)))
            except ValueError:
                days = DEFAULT_HISTORY_DAYS
            since = timezone.now() - timedelta(days=days)
            items = qs.filter(created_at__gte=since)[:200]

        return Response([_serialize(n) for n in items])


class NotificationReadAllView(APIView):
    @extend_schema(summary="通知をすべて既読にする")
    def post(self, request: Request) -> Response:
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response(status=204)


class NotificationReadView(APIView):
    @extend_schema(summary="通知を既読にする")
    def post(self, request: Request, pk: int) -> Response:
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(_serialize(notification))
