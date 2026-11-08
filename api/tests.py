from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from issues.models import Comment, Issue
from projects.models import Project, ProjectMembership


class APISecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="StrongPass123!")
        self.member = User.objects.create_user(username="member", password="StrongPass123!")
        self.stranger = User.objects.create_user(username="stranger", password="StrongPass123!")
        self.project = Project.objects.create(name="Project1", owner=self.owner)
        ProjectMembership.objects.create(project=self.project, user=self.member)
        self.issue = Issue.objects.create(
            project=self.project,
            title="Issue1",
            reporter=self.owner,
            assignee=self.member,
        )
        self.comment = Comment.objects.create(
            issue=self.issue,
            author=self.member,
            content="Project comment",
        )
        self.client = APIClient()

    def test_project_and_issue_endpoints_require_jwt_authentication(self):
        requests = [
            self.client.get("/api/v1/projects/?search=Project1"),
            self.client.post("/api/v1/projects/", {}, format="json"),
            self.client.get(f"/api/v1/projects/{self.project.pk}/"),
            self.client.put(f"/api/v1/projects/{self.project.pk}/", {}, format="json"),
            self.client.patch(f"/api/v1/projects/{self.project.pk}/", {}, format="json"),
            self.client.delete(f"/api/v1/projects/{self.project.pk}/"),
            self.client.get(f"/api/v1/projects/{self.project.pk}/members/"),
            self.client.post(f"/api/v1/projects/{self.project.pk}/members/", {}, format="json"),
            self.client.delete(f"/api/v1/projects/{self.project.pk}/members/{self.member.pk}/"),
            self.client.get("/api/v1/issues/"),
            self.client.post("/api/v1/issues/", {}, format="json"),
            self.client.get(f"/api/v1/issues/{self.issue.pk}/"),
            self.client.put(f"/api/v1/issues/{self.issue.pk}/", {}, format="json"),
            self.client.patch(f"/api/v1/issues/{self.issue.pk}/", {}, format="json"),
            self.client.delete(f"/api/v1/issues/{self.issue.pk}/"),
            self.client.get("/api/v1/comments/"),
            self.client.post("/api/v1/comments/", {}, format="json"),
            self.client.get(f"/api/v1/comments/{self.comment.pk}/"),
            self.client.patch(f"/api/v1/comments/{self.comment.pk}/", {}, format="json"),
            self.client.delete(f"/api/v1/comments/{self.comment.pk}/"),
            self.client.get(f"/api/v1/issues/{self.issue.pk}/comments/"),
            self.client.post(f"/api/v1/issues/{self.issue.pk}/comments/", {}, format="json"),
        ]

        for response in requests:
            with self.subTest(path=response.wsgi_request.path, method=response.wsgi_request.method):
                self.assertEqual(response.status_code, 401)

    def test_web_session_without_jwt_does_not_authenticate_api_requests(self):
        self.client.force_login(self.owner)

        response = self.client.get("/api/v1/projects/?search=Project1")

        self.assertEqual(response.status_code, 401)

    def test_jwt_authentication_and_public_api_surfaces_still_work(self):
        registration = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "api-user",
                "email": "api-user@example.com",
                "password": "AnotherStrongPass123!",
            },
            format="json",
        )
        self.assertEqual(registration.status_code, 201)

        token_response = self.client.post(
            "/api/v1/auth/token/",
            {"username": "owner", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(token_response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.json()['access']}")
        self.assertEqual(self.client.get("/api/v1/projects/").status_code, 200)

        self.client.credentials()
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)

    def test_project_and_issue_data_are_isolated_from_other_users(self):
        self.client.force_authenticate(user=self.stranger)

        project_list = self.client.get("/api/v1/projects/")
        self.assertEqual(project_list.status_code, 200)
        self.assertNotIn(self.project.pk, [item["id"] for item in project_list.json()["results"]])
        self.assertEqual(self.client.get(f"/api/v1/projects/{self.project.pk}/").status_code, 404)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/projects/{self.project.pk}/",
                {"name": "Unauthorized change"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete(f"/api/v1/projects/{self.project.pk}/").status_code, 404)

        self.assertEqual(
            self.client.post(
                "/api/v1/issues/",
                {"project": self.project.pk, "title": "Unauthorized issue"},
                format="json",
            ).status_code,
            403,
        )
        issue_list = self.client.get("/api/v1/issues/")
        self.assertEqual(issue_list.status_code, 200)
        self.assertNotIn(self.issue.pk, [item["id"] for item in issue_list.json()["results"]])
        self.assertEqual(self.client.get(f"/api/v1/issues/{self.issue.pk}/").status_code, 404)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/issues/{self.issue.pk}/",
                {"title": "Unauthorized change"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete(f"/api/v1/issues/{self.issue.pk}/").status_code, 404)

        self.project.refresh_from_db()
        self.issue.refresh_from_db()
        self.assertEqual(self.project.name, "Project1")
        self.assertEqual(self.issue.title, "Issue1")

    def test_issue_comments_are_scoped_to_accessible_projects(self):
        self.client.force_authenticate(user=self.stranger)

        response = self.client.get(f"/api/v1/issues/{self.issue.pk}/comments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(
            self.client.post(
                f"/api/v1/issues/{self.issue.pk}/comments/",
                {"content": "Unauthorized comment"},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/comments/",
                {"issue": self.issue.pk, "content": "Unauthorized comment"},
                format="json",
            ).status_code,
            403,
        )
