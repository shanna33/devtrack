from rest_framework import permissions


class IsProjectAccessAllowed(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.user_can_access(request.user)


class IsProjectEditor(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user_can_manage_project(request.user)


class IsProjectDeleter(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user_can_delete(request.user)


class IsIssueAccessAllowed(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.user_can_access(request.user)
        if request.method == "DELETE":
            return obj.user_can_delete(request.user)
        return obj.user_can_edit(request.user)


class IsCommentAuthorOrProjectOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.user_can_access(request.user)
        return obj.user_can_edit(request.user)
