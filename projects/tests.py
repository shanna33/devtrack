from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from issues.models import Comment, Issue

from .models import Project, ProjectMembership


class ProjectRoleWebTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="StrongPass123!")
        self.manager = User.objects.create_user(username="manager", password="StrongPass123!")
        self.member = User.objects.create_user(username="member", password="StrongPass123!")
        self.stranger = User.objects.create_user(username="stranger", password="StrongPass123!")
        self.project = Project.objects.create(name="Project", owner=self.owner)
        ProjectMembership.objects.create(project=self.project, user=self.owner, role=ProjectMembership.OWNER)
        ProjectMembership.objects.create(project=self.project, user=self.manager, role=ProjectMembership.MANAGER)
        ProjectMembership.objects.create(project=self.project, user=self.member, role=ProjectMembership.MEMBER)
        self.issue = Issue.objects.create(
            project=self.project,
            title="Assigned issue",
            reporter=self.owner,
            assignee=self.member,
        )

    def test_manager_can_edit_project_manage_members_and_manage_issues(self):
        self.client.login(username="manager", password="StrongPass123!")

        self.assertEqual(self.client.get(reverse("project_update", args=[self.project.pk])).status_code, 200)
        response = self.client.post(
            reverse("project_update", args=[self.project.pk]),
            {"name": "Updated project", "description": "Updated by manager"},
        )
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Updated project")

        added_user = User.objects.create_user(username="added", password="StrongPass123!")
        response = self.client.post(
            reverse("project_add_member", args=[self.project.pk]),
            {"username": added_user.username, "role": ProjectMembership.MANAGER},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectMembership.objects.filter(project=self.project, user=added_user, role=ProjectMembership.MANAGER).exists())

        response = self.client.post(
            reverse("project_update_member_role", args=[self.project.pk, self.member.pk]),
            {"role": ProjectMembership.MANAGER},
        )
        self.assertEqual(response.status_code, 302)
        self.member.project_memberships.get(project=self.project).refresh_from_db()
        self.assertEqual(self.member.project_memberships.get(project=self.project).role, ProjectMembership.MANAGER)

        response = self.client.post(
            reverse("project_update_member_role", args=[self.project.pk, self.member.pk]),
            {"role": ProjectMembership.OWNER},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.member.project_memberships.get(project=self.project).role, ProjectMembership.MANAGER)

        owner_membership = self.owner.project_memberships.get(project=self.project)
        self.client.post(
            reverse("project_update_member_role", args=[self.project.pk, self.owner.pk]),
            {"role": ProjectMembership.MEMBER},
        )
        self.client.post(reverse("project_remove_member", args=[self.project.pk, self.owner.pk]))
        owner_membership.refresh_from_db()
        self.assertEqual(owner_membership.role, ProjectMembership.OWNER)

        response = self.client.post(
            reverse("issue_update", args=[self.issue.pk]),
            {
                "title": "Manager updated issue",
                "description": "",
                "status": Issue.STATUS_IN_PROGRESS,
                "priority": Issue.PRIORITY_HIGH,
                "assignee": self.owner.pk,
                "due_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, "Manager updated issue")
        self.assertEqual(self.issue.assignee, self.owner)

        self.client.post(reverse("project_remove_member", args=[self.project.pk, added_user.pk]))
        self.assertFalse(ProjectMembership.objects.filter(project=self.project, user=added_user).exists())
        self.client.post(reverse("project_delete", args=[self.project.pk]))
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

        comment = Comment.objects.create(issue=self.issue, author=self.member, content="Member note")
        response = self.client.post(reverse("delete_comment", args=[comment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_member_can_view_create_comment_and_edit_only_assigned_issues(self):
        self.client.login(username="member", password="StrongPass123!")
        project_detail = self.client.get(reverse("project_detail", args=[self.project.pk]))
        self.assertEqual(project_detail.status_code, 200)
        self.assertNotContains(project_detail, reverse("project_update", args=[self.project.pk]))
        self.assertEqual(self.client.get(reverse("project_members", args=[self.project.pk])).status_code, 200)

        response = self.client.post(
            reverse("project_update", args=[self.project.pk]),
            {"name": "Unauthorized", "description": "Unauthorized"},
        )
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Project")

        new_user = User.objects.create_user(username="newuser", password="StrongPass123!")
        self.client.post(reverse("project_add_member", args=[self.project.pk]), {"username": new_user.username})
        self.assertFalse(ProjectMembership.objects.filter(project=self.project, user=new_user).exists())

        response = self.client.post(
            reverse("issue_update", args=[self.issue.pk]),
            {
                "title": "Member updated assigned issue",
                "description": "",
                "status": Issue.STATUS_IN_PROGRESS,
                "priority": Issue.PRIORITY_MEDIUM,
                "assignee": self.owner.pk,
                "due_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, "Member updated assigned issue")
        self.assertEqual(self.issue.assignee, self.member)

        unassigned_issue = Issue.objects.create(project=self.project, title="Unassigned", reporter=self.owner)
        self.client.post(
            reverse("issue_update", args=[unassigned_issue.pk]),
            {"title": "Unauthorized edit", "description": "", "status": Issue.STATUS_TODO, "priority": Issue.PRIORITY_LOW, "assignee": ""},
        )
        unassigned_issue.refresh_from_db()
        self.assertEqual(unassigned_issue.title, "Unassigned")
        self.client.post(reverse("issue_delete", args=[self.issue.pk]))
        self.assertTrue(Issue.objects.filter(pk=self.issue.pk).exists())

        response = self.client.post(reverse("add_comment", args=[self.issue.pk]), {"content": "Member comment"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Comment.objects.filter(issue=self.issue, author=self.member, content="Member comment").exists())

    def test_owner_can_delete_project_and_manage_every_project_issue(self):
        self.client.login(username="owner", password="StrongPass123!")
        response = self.client.post(
            reverse("issue_update", args=[self.issue.pk]),
            {
                "title": "Owner updated issue",
                "description": "",
                "status": Issue.STATUS_DONE,
                "priority": Issue.PRIORITY_URGENT,
                "assignee": self.member.pk,
                "due_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.title, "Owner updated issue")

        self.client.post(reverse("issue_delete", args=[self.issue.pk]))
        self.assertFalse(Issue.objects.filter(pk=self.issue.pk).exists())
        response = self.client.post(reverse("project_delete", args=[self.project.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_nonmember_cannot_access_project_or_issue(self):
        self.client.login(username="stranger", password="StrongPass123!")
        self.assertEqual(self.client.get(reverse("project_detail", args=[self.project.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("project_members", args=[self.project.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("issue_detail", args=[self.issue.pk])).status_code, 302)


class ProjectRoleAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="api-owner", password="StrongPass123!")
        self.manager = User.objects.create_user(username="api-manager", password="StrongPass123!")
        self.member = User.objects.create_user(username="api-member", password="StrongPass123!")
        self.stranger = User.objects.create_user(username="api-stranger", password="StrongPass123!")
        self.project = Project.objects.create(name="API project", owner=self.owner)
        ProjectMembership.objects.create(project=self.project, user=self.owner, role=ProjectMembership.OWNER)
        ProjectMembership.objects.create(project=self.project, user=self.manager, role=ProjectMembership.MANAGER)
        ProjectMembership.objects.create(project=self.project, user=self.member, role=ProjectMembership.MEMBER)
        self.issue = Issue.objects.create(
            project=self.project,
            title="API issue",
            reporter=self.owner,
            assignee=self.member,
        )
        self.client = APIClient()

    def test_manager_can_manage_project_members_and_issues_but_not_project_ownership(self):
        self.client.force_authenticate(user=self.manager)
        project_url = f"/api/v1/projects/{self.project.pk}/"
        members_url = f"/api/v1/projects/{self.project.pk}/members/"
        response = self.client.patch(project_url, {"name": "Manager edit"}, format="json")
        self.assertEqual(response.status_code, 200)

        added_user = User.objects.create_user(username="api-added", password="StrongPass123!")
        response = self.client.post(
            members_url,
            {"user_id": added_user.pk, "role": ProjectMembership.MANAGER},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        role_url = f"/api/v1/projects/{self.project.pk}/members/{self.member.pk}/role/"
        response = self.client.patch(role_url, {"role": ProjectMembership.MANAGER}, format="json")
        self.assertEqual(response.status_code, 200)
        response = self.client.patch(role_url, {"role": ProjectMembership.OWNER}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/projects/{self.project.pk}/members/{self.manager.pk}/role/",
                {"role": ProjectMembership.OWNER},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/projects/{self.project.pk}/members/{self.owner.pk}/role/",
                {"role": ProjectMembership.MEMBER},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/projects/{self.project.pk}/members/{self.owner.pk}/").status_code,
            400,
        )

        response = self.client.post(
            "/api/v1/issues/",
            {
                "project": self.project.pk,
                "title": "Manager-created issue",
                "assignee": self.member.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        assigned_issue_id = response.json()["id"]
        response = self.client.patch(
            f"/api/v1/issues/{assigned_issue_id}/",
            {"assignee": self.owner.pk, "title": "Manager-assigned issue"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assignee"], self.owner.username)
        self.assertEqual(self.client.delete(f"/api/v1/issues/{assigned_issue_id}/").status_code, 204)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/comments/{Comment.objects.create(issue=self.issue, author=self.member, content='Hi').pk}/",
                {"content": "Manager moderation"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(project_url).status_code, 403)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

        self.assertEqual(self.client.delete(f"/api/v1/projects/{self.project.pk}/members/{added_user.pk}/").status_code, 204)
        other_project = Project.objects.create(name="Other project", owner=self.stranger)
        other_issue = Issue.objects.create(project=other_project, title="Private issue", reporter=self.stranger)
        self.assertEqual(self.client.patch(f"/api/v1/projects/{other_project.pk}/", {"name": "Blocked"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/issues/{other_issue.pk}/").status_code, 404)

    def test_member_api_permissions_and_project_isolation(self):
        self.client.force_authenticate(user=self.member)
        project_url = f"/api/v1/projects/{self.project.pk}/"
        self.assertEqual(self.client.get(project_url).status_code, 200)
        self.assertEqual(self.client.patch(project_url, {"name": "Blocked"}, format="json").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/api/v1/projects/{self.project.pk}/members/",
                {"username": "api-stranger"},
                format="json",
            ).status_code,
            403,
        )

        self.assertEqual(
            self.client.patch(
                f"/api/v1/issues/{self.issue.pk}/",
                {"title": "Member edited assigned issue"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/issues/{self.issue.pk}/",
                {"assignee": self.owner.pk},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(self.client.delete(f"/api/v1/issues/{self.issue.pk}/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/v1/comments/",
                {"issue": self.issue.pk, "content": "Member API comment"},
                format="json",
            ).status_code,
            201,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/issues/",
                {"project": self.project.pk, "title": "Member-created issue", "assignee": self.member.pk},
                format="json",
            ).status_code,
            201,
        )
        another_comment = Comment.objects.create(issue=self.issue, author=self.owner, content="Owner note")
        self.assertEqual(self.client.delete(f"/api/v1/comments/{another_comment.pk}/").status_code, 403)

        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(self.client.get(project_url).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/issues/{self.issue.pk}/").status_code, 404)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/issues/{self.issue.pk}/",
                {"title": "Unauthorized"},
                format="json",
            ).status_code,
            404,
        )

    def test_superuser_can_manage_projects_outside_membership(self):
        admin = User.objects.create_superuser(username="site-admin", password="StrongPass123!")
        self.client.force_authenticate(user=admin)
        response = self.client.get("/api/v1/projects/")
        self.assertIn(self.project.pk, [item["id"] for item in response.json()["results"]])
        response = self.client.patch(
            f"/api/v1/projects/{self.project.pk}/",
            {"description": "Updated by superuser"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/projects/{self.project.pk}/").status_code, 204)
