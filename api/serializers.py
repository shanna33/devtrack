from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from issues.models import Comment, Issue
from projects.models import Project, ProjectMembership


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "name", "description", "owner", "member_count", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at", "member_count"]

    def get_member_count(self, obj: Project) -> int:
        return obj.memberships.count()


class ProjectMembershipSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMembership
        fields = ["id", "user", "username", "role", "joined_at"]
        read_only_fields = ["id", "username", "joined_at"]

    def get_username(self, obj: ProjectMembership) -> str:
        return obj.user.username


class ProjectMembershipRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[ProjectMembership.MEMBER, ProjectMembership.MANAGER])


class AssigneeField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return value.username


class IssueSerializer(serializers.ModelSerializer):
    reporter = serializers.StringRelatedField(read_only=True)
    assignee = AssigneeField(queryset=User.objects.all(), required=False, allow_null=True)
    project = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Issue
        fields = ["id", "project", "title", "description", "status", "priority", "reporter", "assignee", "due_date", "created_at", "updated_at"]
        read_only_fields = ["id", "project", "reporter", "created_at", "updated_at"]

    def validate_assignee(self, value):
        project = getattr(self.instance, "project", None) or self.context.get("project")
        request = self.context.get("request")
        if value is None:
            return value
        if project is None:
            raise serializers.ValidationError("A project context is required to validate assignee membership.")
        if value.id != project.owner_id and not project.memberships.filter(user_id=value.id).exists():
            raise serializers.ValidationError("Assignee must be a project member or the project owner.")
        if request and not project.user_can_manage_project(request.user) and value.id != request.user.id:
            raise serializers.ValidationError("Only project managers can assign issues to other members.")
        return value

    def validate(self, attrs):
        project = getattr(self.instance, "project", None) or self.context.get("project")
        request = self.context.get("request")
        if (
            self.instance is not None
            and "assignee" in attrs
            and project is not None
            and request is not None
            and not project.user_can_manage_project(request.user)
            and attrs["assignee"] != self.instance.assignee
        ):
            raise serializers.ValidationError({"assignee": "Only project managers can change issue assignments."})
        return attrs


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    issue = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "issue", "author", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "issue", "author", "created_at", "updated_at"]
