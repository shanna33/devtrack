from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    CommentViewSet,
    IssueCommentsAPIView,
    IssueViewSet,
    ProjectMembershipAPIView,
    ProjectMembershipDestroyAPIView,
    ProjectMembershipRoleAPIView,
    ProjectViewSet,
    RegisterView,
)

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"issues", IssueViewSet, basename="issue")
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="api_token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),
    path("auth/register/", RegisterView.as_view(), name="api_register"),
    path("projects/<int:project_id>/members/", ProjectMembershipAPIView.as_view(), name="api_project_members"),
    path("projects/<int:project_id>/members/<int:user_id>/", ProjectMembershipDestroyAPIView.as_view(), name="api_project_members_remove"),
    path("projects/<int:project_id>/members/<int:user_id>/role/", ProjectMembershipRoleAPIView.as_view(), name="api_project_member_role"),
    path("issues/<int:issue_id>/comments/", IssueCommentsAPIView.as_view(), name="api_issue_comments"),
    path("", include(router.urls)),
]
