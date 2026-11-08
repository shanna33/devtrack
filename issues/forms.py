from django import forms

from projects.models import ProjectMembership

from .models import Comment, Issue


class IssueForm(forms.ModelForm):
    def __init__(self, *args, project=None, user=None, can_assign=True, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            members = [project.owner] + [m.user for m in project.memberships.select_related("user").all()]
            self.fields["assignee"].queryset = self.fields["assignee"].queryset.filter(pk__in=[u.pk for u in members])
        if not can_assign:
            self.fields["assignee"].queryset = self.fields["assignee"].queryset.filter(pk=getattr(user, "pk", None))
            self.fields["assignee"].disabled = bool(self.instance.pk)

    class Meta:
        model = Issue
        fields = ["title", "description", "status", "priority", "assignee", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "assignee": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {"content": forms.Textarea(attrs={"class": "form-control", "rows": 3})}
