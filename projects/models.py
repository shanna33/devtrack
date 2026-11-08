from django.conf import settings
from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="owned_projects", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.count()

    def user_can_access(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if self.owner_id == user.id:
            return True
        return self.memberships.filter(user_id=user.id).exists()

    def user_can_manage_project(self, user):
        if not user.is_authenticated:
            return False
        if user.is_superuser or self.owner_id == user.id:
            return True
        return self.memberships.filter(user_id=user.id, role=ProjectMembership.MANAGER).exists()

    def user_can_delete(self, user):
        return user.is_authenticated and (user.is_superuser or self.owner_id == user.id)


class ProjectMembership(models.Model):
    OWNER = "owner"
    MEMBER = "member"
    MANAGER = "manager"
    ROLE_CHOICES = [(OWNER, "Owner"), (MANAGER, "Manager"), (MEMBER, "Member")]

    project = models.ForeignKey(Project, related_name="memberships", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="project_memberships", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_membership"),
        ]
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} in {self.project.name}"
