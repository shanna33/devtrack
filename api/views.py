from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import OpenApiParameter, extend_schema

from issues.models import Comment, Issue
from projects.models import Project, ProjectMembership

from .permissions import (
    IsCommentAuthorOrProjectOwner,
    IsIssueAccessAllowed,
    IsProjectAccessAllowed,
    IsProjectDeleter,
    IsProjectEditor,
)
from .serializers import (
    CommentSerializer,
    IssueSerializer,
    ProjectMembershipCreateSerializer,
    ProjectMembershipDeleteSerializer,
    ProjectMembershipRoleSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    RegisterSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectAccessAllowed]
    filterset_fields = ["owner"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_queryset(self):
        projects = Project.objects.all() if self.request.user.is_superuser else Project.objects.filter(
            Q(owner=self.request.user) | Q(memberships__user=self.request.user)
        ).distinct()
        return projects.select_related("owner").prefetch_related("memberships__user")

    def perform_create(self, serializer):
        project = serializer.save(owner=self.request.user)
        ProjectMembership.objects.create(project=project, user=self.request.user, role=ProjectMembership.OWNER)

    def get_permissions(self):
        if self.action in ["update", "partial_update"]:
            self.permission_classes = [permissions.IsAuthenticated, IsProjectEditor]
        elif self.action == "destroy":
            self.permission_classes = [permissions.IsAuthenticated, IsProjectDeleter]
        return super().get_permissions()


class ProjectMembershipAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_project(self, project_id):
        project = Project.objects.filter(pk=project_id).first()
        if project is None:
            return None
        if not project.user_can_access(self.request.user):
            return None
        return project

    @extend_schema(responses=ProjectMembershipSerializer(many=True))
    def get(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Project not found or inaccessible."}, status=status.HTTP_404_NOT_FOUND)
        memberships = ProjectMembership.objects.filter(project=project).select_related("user")
        serializer = ProjectMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=ProjectMembershipCreateSerializer,
        responses={status.HTTP_201_CREATED: ProjectMembershipSerializer},
    )
    def post(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Project not found or inaccessible."}, status=status.HTTP_404_NOT_FOUND)
        if not project.user_can_manage_project(request.user):
            return Response({"detail": "You do not have permission to manage project members."}, status=status.HTTP_403_FORBIDDEN)

        input_serializer = ProjectMembershipCreateSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = input_serializer.validated_data["member"]
        if user == project.owner:
            return Response({"detail": "Project owner is already included."}, status=status.HTTP_400_BAD_REQUEST)
        role = input_serializer.validated_data["role"]
        membership, created = ProjectMembership.objects.get_or_create(
            project=project,
            user=user,
            defaults={"role": role},
        )
        if not created:
            return Response({"detail": "This user is already a member."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ProjectMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="project_members_remove_legacy",
        request=ProjectMembershipDeleteSerializer,
        responses={status.HTTP_204_NO_CONTENT: None},
    )
    def delete(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Project not found or inaccessible."}, status=status.HTTP_404_NOT_FOUND)
        if not project.user_can_manage_project(request.user):
            return Response({"detail": "You do not have permission to manage project members."}, status=status.HTTP_403_FORBIDDEN)
        input_serializer = ProjectMembershipDeleteSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user_id = input_serializer.validated_data["user_id"]
        membership = ProjectMembership.objects.filter(project=project, user_id=user_id).first()
        if not membership:
            return Response({"detail": "Membership not found."}, status=status.HTTP_404_NOT_FOUND)
        if membership.user == project.owner:
            return Response({"detail": "Project owner cannot be removed."}, status=status.HTTP_400_BAD_REQUEST)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectMemberSearchAPIView(APIView):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Username search term (at least 2 characters).",
            )
        ],
        responses={status.HTTP_200_OK: dict},
    )
    def get(self, request, project_id):
        project = Project.objects.filter(pk=project_id).first()
        if project is None or not project.user_can_access(request.user):
            return Response(
                {"detail": "Project not found or inaccessible."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not project.user_can_manage_project(request.user):
            return Response(
                {"detail": "You do not have permission to search for project members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"detail": "Search term must contain at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_member_ids = ProjectMembership.objects.filter(
            project=project
        ).values("user_id")
        users = (
            User.objects.filter(username__icontains=query)
            .exclude(pk=project.owner_id)
            .exclude(pk__in=existing_member_ids)
            .order_by("username")
            .values("id", "username", "email")[:10]
        )
        return Response({"results": list(users)})


class IssueViewSet(viewsets.ModelViewSet):
    serializer_class = IssueSerializer
    permission_classes = [permissions.IsAuthenticated, IsIssueAccessAllowed]
    filterset_fields = ["project", "status", "priority", "assignee"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "due_date", "priority"]

    def get_queryset(self):
        accessible_projects = Project.objects.all() if self.request.user.is_superuser else Project.objects.filter(
            Q(owner=self.request.user) | Q(memberships__user=self.request.user)
        ).distinct()
        return Issue.objects.filter(project__in=accessible_projects).select_related("project", "reporter", "assignee")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in ["create", "update", "partial_update"]:
            project_id = self.request.data.get("project")
            if project_id:
                context["project"] = Project.objects.filter(pk=project_id).first()
        return context

    def perform_create(self, serializer):
        project_id = self.request.data.get("project")
        project = Project.objects.filter(pk=project_id).first()
        if not project or not project.user_can_access(self.request.user):
            raise PermissionDenied("You do not have access to this project.")
        serializer.save(reporter=self.request.user, project=project)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommentAuthorOrProjectOwner]

    def get_queryset(self):
        accessible_projects = Project.objects.all() if self.request.user.is_superuser else Project.objects.filter(
            Q(owner=self.request.user) | Q(memberships__user=self.request.user)
        ).distinct()
        return Comment.objects.filter(issue__project__in=accessible_projects).select_related("issue", "author")

    def perform_create(self, serializer):
        issue_id = self.request.data.get("issue")
        issue = Issue.objects.filter(pk=issue_id).first()
        if not issue or not issue.user_can_access(self.request.user):
            raise PermissionDenied("You cannot comment on inaccessible issues.")
        serializer.save(author=self.request.user, issue=issue)


class IssueCommentsAPIView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        issue = Issue.objects.filter(pk=self.kwargs["issue_id"]).first()
        if issue is None or not issue.user_can_access(self.request.user):
            return Comment.objects.none()
        return Comment.objects.filter(issue=issue).select_related("author")

    def perform_create(self, serializer):
        issue = Issue.objects.filter(pk=self.kwargs["issue_id"]).first()
        if issue is None or not issue.user_can_access(self.request.user):
            raise PermissionDenied("You cannot comment on inaccessible issues.")
        serializer.save(author=self.request.user, issue=issue)


class ProjectMembershipDestroyAPIView(generics.DestroyAPIView):
    serializer_class = ProjectMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProjectMembership.objects.all()

    @extend_schema(
        operation_id="project_member_remove",
        responses={status.HTTP_204_NO_CONTENT: None},
    )
    def delete(self, request, *args, **kwargs):
        project = Project.objects.filter(pk=self.kwargs["project_id"]).first()
        if project is None or not project.user_can_access(request.user):
            return Response({"detail": "Project not found or inaccessible."}, status=status.HTTP_404_NOT_FOUND)
        if not project.user_can_manage_project(request.user):
            return Response({"detail": "You do not have permission to manage project members."}, status=status.HTTP_403_FORBIDDEN)
        membership = ProjectMembership.objects.filter(project=project, user_id=self.kwargs["user_id"]).first()
        if membership is None:
            return Response({"detail": "Membership not found."}, status=status.HTTP_404_NOT_FOUND)
        if membership.user == project.owner:
            return Response({"detail": "Project owner cannot be removed."}, status=status.HTTP_400_BAD_REQUEST)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectMembershipRoleAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ProjectMembershipRoleSerializer, responses=ProjectMembershipSerializer)
    def patch(self, request, project_id, user_id):
        project = Project.objects.filter(pk=project_id).first()
        if project is None or not project.user_can_access(request.user):
            return Response({"detail": "Project not found or inaccessible."}, status=status.HTTP_404_NOT_FOUND)
        if not project.user_can_manage_project(request.user):
            return Response({"detail": "You do not have permission to manage project members."}, status=status.HTTP_403_FORBIDDEN)
        membership = ProjectMembership.objects.filter(project=project, user_id=user_id).select_related("user").first()
        if membership is None:
            return Response({"detail": "Membership not found."}, status=status.HTTP_404_NOT_FOUND)
        if membership.user_id == project.owner_id:
            return Response({"detail": "The project owner's role cannot be changed."}, status=status.HTTP_400_BAD_REQUEST)
        role = request.data.get("role")
        if role not in (ProjectMembership.MEMBER, ProjectMembership.MANAGER):
            return Response({"detail": "A member can only be assigned the member or manager role."}, status=status.HTTP_400_BAD_REQUEST)
        membership.role = role
        membership.save(update_fields=["role"])
        return Response(ProjectMembershipSerializer(membership).data)
