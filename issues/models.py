from django.conf import settings
from django.db import models

from projects.models import Project


class Issue(models.Model):
    STATUS_TODO = "TODO"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_IN_REVIEW = "IN_REVIEW"
    STATUS_DONE = "DONE"
    STATUS_CHOICES = [
        (STATUS_TODO, "To do"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_IN_REVIEW, "In review"),
        (STATUS_DONE, "Done"),
    ]

    PRIORITY_LOW = "LOW"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_URGENT = "URGENT"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_URGENT, "Urgent"),
    ]

    project = models.ForeignKey(Project, related_name="issues", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TODO)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reported_issues", on_delete=models.CASCADE)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assigned_issues", null=True, blank=True, on_delete=models.SET_NULL)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "priority"]),
            models.Index(fields=["project", "assignee"]),
        ]

    def __str__(self):
        return self.title

    def user_can_access(self, user):
        if not user.is_authenticated:
            return False
        return self.project.user_can_access(user)

    def user_can_edit(self, user):
        if not user.is_authenticated or not self.project.user_can_access(user):
            return False
        return self.project.user_can_manage_project(user) or self.assignee_id == user.id

    def user_can_delete(self, user):
        return self.user_can_access(user) and self.project.user_can_manage_project(user)

    def clean(self):
        super().clean()
        if self.assignee_id and self.project_id:
            allowed = self.project.memberships.filter(user_id=self.assignee_id).exists() or self.project.owner_id == self.assignee_id
            if not allowed:
                raise models.ValidationError({"assignee": "Assignee must be a project member or the project owner."})


class Comment(models.Model):
    issue = models.ForeignKey("Issue", related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="comments", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.issue.title}"

    def user_can_access(self, user):
        if not user.is_authenticated:
            return False
        return self.issue.user_can_access(user)

    def user_can_edit(self, user):
        if not user.is_authenticated:
            return False
        return self.author_id == user.id or self.issue.project.user_can_manage_project(user)
