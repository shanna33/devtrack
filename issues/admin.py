from django.contrib import admin

from .models import Comment, Issue


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "priority", "reporter", "assignee")
    search_fields = ("title", "description", "project__name")
    list_filter = ("status", "priority")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("issue", "author", "created_at")
    search_fields = ("content", "author__username")
