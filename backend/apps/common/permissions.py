from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """role が admin のユーザーのみ許可する。"""

    message = "管理者のみが実行できます。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role)


class IsSelfOrAdmin(BasePermission):
    """本人か管理者のみ。

    正社員のデータ範囲はオブジェクトレベルで制限する（設計書 第9.1章）。
    ビュー側でも get_queryset() を必ず絞ること。この Permission は二重の歯止め。
    """

    message = "自分のデータのみ参照できます。"

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if user.is_admin_role:
            return True
        owner_id = getattr(obj, "user_id", None) or getattr(obj, "id", None)
        return owner_id == user.id
