from django import forms
from django.contrib.auth import get_user_model

from .models import Project, ProjectMembership


User = get_user_model()


class ProjectMemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.username} ({obj.email})" if obj.email else obj.username


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class ProjectMembershipForm(forms.ModelForm):
    user = ProjectMemberChoiceField(
        queryset=User.objects.none(),
        label="Registered user",
        error_messages={
            "invalid_choice": "Choose a registered user who is not already a project member."
        },
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    role = forms.ChoiceField(
        choices=[
            (ProjectMembership.MEMBER, "Member"),
            (ProjectMembership.MANAGER, "Manager"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        existing_member_ids = ProjectMembership.objects.filter(project=project).values("user_id")
        self.fields["user"].queryset = (
            User.objects.exclude(pk=project.owner_id)
            .exclude(pk__in=existing_member_ids)
            .order_by("username")
        )

    def clean_user(self):
        user = self.cleaned_data["user"]
        if ProjectMembership.objects.filter(project=self.project, user=user).exists():
            raise forms.ValidationError("This user is already a project member.")
        return user

    class Meta:
        model = ProjectMembership
        fields = ["user", "role"]
