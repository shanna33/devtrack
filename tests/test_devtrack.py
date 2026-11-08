from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from issues.models import Comment, Issue
from projects.models import Project, ProjectMembership


class DevTrackTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="StrongPass123!")
        self.member = User.objects.create_user(username="member", password="StrongPass123!")
        self.other = User.objects.create_user(username="stranger", password="StrongPass123!")
        self.project = Project.objects.create(name="Alpha", description="Project alpha", owner=self.owner)
        ProjectMembership.objects.create(project=self.project, user=self.member, role=ProjectMembership.MEMBER)

    def test_registration_works(self):
        response = self.client.post(
            "/accounts/register/",
            {"username": "newuser", "email": "new@example.com", "password1": "StrongPass123!", "password2": "StrongPass123!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_login_works(self):
        response = self.client.post("/accounts/login/", {"username": "owner", "password": "StrongPass123!"}, follow=True)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_anonymous_user_cannot_access_protected_pages(self):
        response = self.client.get("/", follow=True)
        self.assertRedirects(response, "/accounts/login/?next=/")

    def test_authenticated_user_can_create_project(self):
        self.client.login(username="owner", password="StrongPass123!")
        response = self.client.post("/projects/new/", {"name": "Beta", "description": "Second project"})
        self.assertRedirects(response, "/projects/2/")
        self.assertTrue(Project.objects.filter(name="Beta").exists())

    def test_owner_can_update_project(self):
        self.client.login(username="owner", password="StrongPass123!")
        response = self.client.post(f"/projects/{self.project.pk}/edit/", {"name": "Alpha Updated", "description": "Updated"})
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Alpha Updated")
        self.assertEqual(response.status_code, 302)

    def test_unauthorized_user_cannot_access_private_project(self):
        self.client.login(username="stranger", password="StrongPass123!")
        response = self.client.get(f"/projects/{self.project.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_duplicate_membership_is_prevented(self):
        with self.assertRaises(IntegrityError):
            ProjectMembership.objects.create(project=self.project, user=self.member, role=ProjectMembership.MEMBER)

    def test_member_can_create_issue(self):
        self.client.login(username="member", password="StrongPass123!")
        response = self.client.post(f"/issues/new/{self.project.pk}/", {
            "title": "Fix login bug",
            "description": "Add proper validation",
            "status": Issue.STATUS_IN_PROGRESS,
            "priority": Issue.PRIORITY_HIGH,
            "assignee": self.member.pk,
            "due_date": "2026-12-10",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Issue.objects.filter(title="Fix login bug").exists())

    def test_invalid_assignee_is_rejected(self):
        self.client.login(username="member", password="StrongPass123!")
        response = self.client.post(f"/issues/new/{self.project.pk}/", {
            "title": "Bad issue",
            "description": "Should not happen",
            "status": Issue.STATUS_TODO,
            "priority": Issue.PRIORITY_MEDIUM,
            "assignee": self.other.pk,
        })
        self.assertContains(response, "Assignee")

    def test_unauthorized_user_cannot_access_issue(self):
        issue = Issue.objects.create(project=self.project, title="Issue A", description="Desc", reporter=self.owner, assignee=self.member)
        self.client.login(username="other", password="StrongPass123!")
        response = self.client.get(f"/issues/{issue.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_authorized_user_can_comment(self):
        issue = Issue.objects.create(project=self.project, title="Issue B", description="Desc", reporter=self.owner, assignee=self.member)
        self.client.login(username="member", password="StrongPass123!")
        response = self.client.post(f"/issues/{issue.pk}/comments/add/", {"content": "Looks good"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(content="Looks good").exists())

    def test_unauthorized_user_cannot_comment(self):
        issue = Issue.objects.create(project=self.project, title="Issue C", description="Desc", reporter=self.owner, assignee=self.member)
        self.client.login(username="stranger", password="StrongPass123!")
        response = self.client.post(f"/issues/{issue.pk}/comments/add/", {"content": "No access"})
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_delete_another_users_comment(self):
        issue = Issue.objects.create(project=self.project, title="Issue D", description="Desc", reporter=self.owner, assignee=self.member)
        comment = Comment.objects.create(issue=issue, author=self.member, content="Member comment")
        self.client.login(username="stranger", password="StrongPass123!")
        response = self.client.post(f"/issues/comments/{comment.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_api_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/v1/projects/")
        self.assertEqual(response.status_code, 401)

    def test_api_scopes_querysets_and_pagination(self):
        client = APIClient()
        client.force_authenticate(user=self.member)
        hidden_project = Project.objects.create(name="Hidden project", owner=self.other)
        for i in range(25):
            Project.objects.create(name=f"P{i}", owner=self.member)
        response = client.get("/api/v1/projects/?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.json())
        self.assertLessEqual(len(response.json()["results"]), 20)
        self.assertNotIn("Hidden project", [item["name"] for item in response.json()["results"]])
