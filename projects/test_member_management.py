from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Project, ProjectMembership


class ProjectMemberManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="roster-owner",
            email="owner@example.com",
            password="StrongPass123!",
        )
        self.manager = User.objects.create_user(
            username="roster-manager",
            email="manager@example.com",
            password="StrongPass123!",
        )
        self.member = User.objects.create_user(
            username="roster-member",
            email="member@example.com",
            password="StrongPass123!",
        )
        self.candidate = User.objects.create_user(
            username="roster-candidate",
            email="candidate@example.com",
            password="StrongPass123!",
        )
        self.stranger = User.objects.create_user(
            username="roster-stranger",
            email="stranger@example.com",
            password="StrongPass123!",
        )
        self.project = Project.objects.create(name="Member project", owner=self.owner)
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.OWNER,
        )
        self.manager_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.manager,
            role=ProjectMembership.MANAGER,
        )
        self.member_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.MEMBER,
        )

    def test_owner_and_manager_see_complete_member_list_and_contact_details(self):
        self.owner.project_memberships.filter(project=self.project).delete()

        for user in (self.owner, self.manager):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("project_members", args=[self.project.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, self.owner.username)
                self.assertContains(response, self.manager.username)
                self.assertContains(response, self.member.username)
                self.assertContains(response, self.owner.email)
                self.assertContains(response, self.manager.email)
                self.assertContains(response, self.member.email)
                self.assertContains(response, "Owner")

    def test_member_can_view_allowed_member_information_but_not_email_or_controls(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("project_members", args=[self.project.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.owner.username)
        self.assertContains(response, self.manager.username)
        self.assertContains(response, self.member.username)
        self.assertNotContains(response, self.owner.email)
        self.assertNotContains(response, self.manager.email)
        self.assertNotContains(response, reverse("project_add_member", args=[self.project.pk]))
        self.assertNotContains(response, "Change role")
        self.assertNotContains(response, "Remove</button>")

    def test_owner_only_project_shows_empty_additional_member_state(self):
        ProjectMembership.objects.filter(project=self.project).exclude(user=self.owner).delete()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("project_members", args=[self.project.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.owner.username)
        self.assertContains(response, "No additional members yet.")

    def test_manager_can_add_a_registered_user_and_form_excludes_ineligible_users(self):
        self.client.force_login(self.manager)
        page = self.client.get(reverse("project_members", args=[self.project.pk]))
        self.assertContains(page, 'type="search"')
        self.assertNotContains(page, f">{self.candidate.username} ({self.candidate.email})</option>")
        self.assertNotContains(page, f">{self.owner.username} ({self.owner.email})</option>")
        self.assertNotContains(page, f">{self.member.username} ({self.member.email})</option>")

        search = self.client.get(
            reverse("api_project_members_search", args=[self.project.pk]),
            {"q": "roster-c"},
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(
            [user["id"] for user in search.json()["results"]],
            [self.candidate.pk],
        )

        response = self.client.post(
            reverse("project_add_member", args=[self.project.pk]),
            {"user": self.candidate.pk, "role": ProjectMembership.MEMBER},
            follow=True,
        )

        self.assertRedirects(response, reverse("project_members", args=[self.project.pk]))
        self.assertTrue(
            ProjectMembership.objects.filter(
                project=self.project,
                user=self.candidate,
                role=ProjectMembership.MEMBER,
            ).exists()
        )
        self.assertContains(response, "was added to the project")

    def test_duplicate_invalid_user_owner_and_invalid_role_are_rejected(self):
        self.client.force_login(self.owner)
        url = reverse("project_add_member", args=[self.project.pk])

        for payload in (
            {"user": self.member.pk, "role": ProjectMembership.MEMBER},
            {"user": 999999, "role": ProjectMembership.MEMBER},
            {"user": "not-a-user", "role": ProjectMembership.MEMBER},
            {"user": self.owner.pk, "role": ProjectMembership.MEMBER},
            {"user": self.candidate.pk, "role": ProjectMembership.OWNER},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["member_form"].errors)

        self.assertEqual(
            ProjectMembership.objects.filter(project=self.project, user=self.member).count(),
            1,
        )
        self.assertFalse(
            ProjectMembership.objects.filter(project=self.project, user=self.candidate).exists()
        )

    def test_owner_can_change_member_role_but_cannot_assign_owner_role(self):
        self.client.force_login(self.owner)
        url = reverse(
            "project_update_member_role",
            args=[self.project.pk, self.member.pk],
        )

        response = self.client.post(url, {"role": ProjectMembership.MANAGER})
        self.assertEqual(response.status_code, 302)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ProjectMembership.MANAGER)

        response = self.client.post(url, {"role": ProjectMembership.OWNER})
        self.assertEqual(response.status_code, 302)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ProjectMembership.MANAGER)

        owner_membership = ProjectMembership.objects.get(project=self.project, user=self.owner)
        self.client.post(
            reverse("project_update_member_role", args=[self.project.pk, self.owner.pk]),
            {"role": ProjectMembership.MEMBER},
        )
        self.client.post(reverse("project_remove_member", args=[self.project.pk, self.owner.pk]))
        owner_membership.refresh_from_db()
        self.assertEqual(owner_membership.role, ProjectMembership.OWNER)

    def test_manager_can_manage_members_but_cannot_change_or_remove_owner(self):
        self.client.force_login(self.manager)
        self.client.post(
            reverse("project_update_member_role", args=[self.project.pk, self.owner.pk]),
            {"role": ProjectMembership.MEMBER},
        )
        self.client.post(reverse("project_remove_member", args=[self.project.pk, self.owner.pk]))

        self.manager_membership.refresh_from_db()
        self.assertEqual(self.manager_membership.role, ProjectMembership.MANAGER)
        self.assertTrue(
            ProjectMembership.objects.filter(project=self.project, user=self.owner).exists()
        )

    def test_member_cannot_add_change_or_remove_members(self):
        self.client.force_login(self.member)
        self.client.post(
            reverse("project_add_member", args=[self.project.pk]),
            {"user": self.candidate.pk, "role": ProjectMembership.MANAGER},
        )
        self.client.post(
            reverse("project_update_member_role", args=[self.project.pk, self.member.pk]),
            {"role": ProjectMembership.MANAGER},
        )
        self.client.post(
            reverse("project_remove_member", args=[self.project.pk, self.member.pk])
        )

        self.assertFalse(
            ProjectMembership.objects.filter(project=self.project, user=self.candidate).exists()
        )
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ProjectMembership.MEMBER)
        self.assertTrue(
            ProjectMembership.objects.filter(project=self.project, user=self.member).exists()
        )

    def test_missing_and_cross_project_membership_ids_are_not_accessible(self):
        other_project = Project.objects.create(name="Other member project", owner=self.stranger)
        other_membership = ProjectMembership.objects.create(
            project=other_project,
            user=self.candidate,
            role=ProjectMembership.MEMBER,
        )
        self.client.force_login(self.manager)

        for url in (
            reverse("project_remove_member", args=[self.project.pk, 999999]),
            reverse("project_update_member_role", args=[self.project.pk, 999999]),
            reverse("project_remove_member", args=[self.project.pk, self.candidate.pk]),
            reverse("project_update_member_role", args=[self.project.pk, self.candidate.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {"role": ProjectMembership.MANAGER}).status_code, 404)

        self.client.force_login(self.stranger)
        response = self.client.get(reverse("project_members", args=[self.project.pk]))
        self.assertEqual(response.status_code, 302)
        other_membership.refresh_from_db()
        self.assertEqual(other_membership.role, ProjectMembership.MEMBER)


class ProjectMemberManagementAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="api-roster-owner", password="StrongPass123!")
        self.manager = User.objects.create_user(username="api-roster-manager", password="StrongPass123!")
        self.member = User.objects.create_user(username="api-roster-member", password="StrongPass123!")
        self.candidate = User.objects.create_user(username="api-roster-candidate", password="StrongPass123!")
        self.project = Project.objects.create(name="API member project", owner=self.owner)
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.OWNER,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.manager,
            role=ProjectMembership.MANAGER,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.manager)
        self.members_url = f"/api/v1/projects/{self.project.pk}/members/"

    def test_api_add_validates_existing_users_roles_and_duplicates(self):
        invalid_id = self.client.post(
            self.members_url,
            {"user_id": "not-an-id", "role": ProjectMembership.MEMBER},
            format="json",
        )
        self.assertEqual(invalid_id.status_code, 400)

        missing_user = self.client.post(
            self.members_url,
            {"username": "not-registered", "role": ProjectMembership.MEMBER},
            format="json",
        )
        self.assertEqual(missing_user.status_code, 400)

        owner_add = self.client.post(
            self.members_url,
            {"user_id": self.owner.pk, "role": ProjectMembership.MEMBER},
            format="json",
        )
        self.assertEqual(owner_add.status_code, 400)

        invalid_role = self.client.post(
            self.members_url,
            {"user_id": self.candidate.pk, "role": ProjectMembership.OWNER},
            format="json",
        )
        self.assertEqual(invalid_role.status_code, 400)

        added = self.client.post(
            self.members_url,
            {"user_id": self.candidate.pk, "role": ProjectMembership.MEMBER},
            format="json",
        )
        self.assertEqual(added.status_code, 201)
        self.assertEqual(
            self.client.post(
                self.members_url,
                {"user_id": self.candidate.pk, "role": ProjectMembership.MEMBER},
                format="json",
            ).status_code,
            400,
        )

        roster = self.client.get(self.members_url)
        self.assertEqual(roster.status_code, 200)
        self.assertEqual(
            {item["username"] for item in roster.json()},
            {self.owner.username, self.manager.username, self.candidate.username},
        )

    def test_api_membership_operations_are_scoped_to_the_project(self):
        other_project = Project.objects.create(name="API other project", owner=self.member)
        other_membership = ProjectMembership.objects.create(
            project=other_project,
            user=self.candidate,
            role=ProjectMembership.MEMBER,
        )

        self.assertEqual(
            self.client.patch(
                f"/api/v1/projects/{self.project.pk}/members/{self.candidate.pk}/role/",
                {"role": ProjectMembership.MANAGER},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/projects/{self.project.pk}/members/{self.candidate.pk}/"
            ).status_code,
            404,
        )
        other_membership.refresh_from_db()
        self.assertEqual(other_membership.role, ProjectMembership.MEMBER)

    def test_api_legacy_delete_validates_user_id_and_removes_member(self):
        invalid_id = self.client.delete(
            self.members_url,
            {"user_id": "not-an-id"},
            format="json",
        )
        self.assertEqual(invalid_id.status_code, 400)

        missing_membership = self.client.delete(
            self.members_url,
            {"user_id": self.candidate.pk},
            format="json",
        )
        self.assertEqual(missing_membership.status_code, 404)

        ProjectMembership.objects.create(
            project=self.project,
            user=self.candidate,
            role=ProjectMembership.MEMBER,
        )
        removed = self.client.delete(
            self.members_url,
            {"user_id": self.candidate.pk},
            format="json",
        )

        self.assertEqual(removed.status_code, 204)
        self.assertFalse(
            ProjectMembership.objects.filter(
                project=self.project,
                user=self.candidate,
            ).exists()
        )


class ProjectMemberSearchAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="directory-owner",
            email="owner@example.com",
            password="StrongPass123!",
        )
        self.manager = User.objects.create_user(
            username="directory-manager",
            email="manager@example.com",
            password="StrongPass123!",
        )
        self.member = User.objects.create_user(
            username="directory-member",
            email="member@example.com",
            password="StrongPass123!",
        )
        self.project = Project.objects.create(name="Directory project", owner=self.owner)
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.OWNER,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.manager,
            role=ProjectMembership.MANAGER,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.MEMBER,
        )
        self.candidate = User.objects.create_user(
            username="directory-match",
            email="match@example.com",
            password="StrongPass123!",
        )
        self.unrelated = User.objects.create_user(
            username="unrelated-account",
            email="unrelated@example.com",
            password="StrongPass123!",
        )
        self.search_url = reverse(
            "api_project_members_search",
            args=[self.project.pk],
        )
        self.client = APIClient()

    def test_owner_and_manager_can_search_with_minimum_user_fields(self):
        for user in (self.owner, self.manager):
            with self.subTest(user=user.username):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.search_url, {"q": "directory-m"})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["results"],
                    [{
                        "id": self.candidate.pk,
                        "username": self.candidate.username,
                        "email": self.candidate.email,
                    }],
                )

    def test_member_and_anonymous_cannot_search(self):
        self.client.force_authenticate(user=self.member)
        self.assertEqual(
            self.client.get(self.search_url, {"q": "un"}).status_code,
            403,
        )

        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(self.search_url, {"q": "un"}).status_code,
            403,
        )

    def test_search_is_scoped_excludes_current_members_and_owner(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(self.search_url, {"q": "directory"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["username"] for item in response.json()["results"]],
            [self.candidate.username],
        )
        self.assertNotIn(
            self.unrelated.username,
            [item["username"] for item in response.json()["results"]],
        )

    def test_search_requires_two_characters_and_limits_results_to_ten(self):
        self.client.force_authenticate(user=self.owner)

        short_query = self.client.get(self.search_url, {"q": "d"})
        self.assertEqual(short_query.status_code, 400)
        self.assertIn("at least 2 characters", short_query.json()["detail"])

        for index in range(12):
            User.objects.create_user(
                username=f"search-target-{index:02}",
                email=f"target-{index}@example.com",
                password="StrongPass123!",
            )

        response = self.client.get(self.search_url, {"q": "search-target"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 10)
        self.assertEqual(
            set(response.json()["results"][0]),
            {"id", "username", "email"},
        )

    def test_member_search_endpoint_rejects_cross_project_access(self):
        other_project = Project.objects.create(name="Private directory", owner=self.unrelated)
        other_search = reverse("api_project_members_search", args=[other_project.pk])
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(other_search, {"q": "un"})

        self.assertEqual(response.status_code, 404)
