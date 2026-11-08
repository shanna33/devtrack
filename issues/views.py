from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projects.models import Project

from .forms import CommentForm, IssueForm
from .models import Comment, Issue


@login_required
def issue_list(request):
    project_id = request.GET.get("project")
    status = request.GET.get("status")
    priority = request.GET.get("priority")
    assignee = request.GET.get("assignee")
    search = request.GET.get("search", "")
    ordering = request.GET.get("ordering", "-updated_at")

    projects = Project.objects.all() if request.user.is_superuser else Project.objects.filter(
        Q(owner=request.user) | Q(memberships__user=request.user)
    ).distinct()
    issues = Issue.objects.select_related("project", "reporter", "assignee").filter(project__in=projects)

    if project_id:
        issues = issues.filter(project_id=project_id)
    if status:
        issues = issues.filter(status=status)
    if priority:
        issues = issues.filter(priority=priority)
    if assignee:
        issues = issues.filter(assignee_id=assignee)
    if search:
        issues = issues.filter(Q(title__icontains=search) | Q(description__icontains=search))

    allowed_order = ["created_at", "updated_at", "due_date", "priority"]
    if ordering in allowed_order or ordering.startswith("-") and ordering[1:] in allowed_order:
        issues = issues.order_by(ordering)
    else:
        issues = issues.order_by("-updated_at")

    paginator = Paginator(issues, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "issues/issue_list.html", {
        "issues": page_obj,
        "projects": projects,
        "selected_project": project_id,
        "selected_status": status,
        "selected_priority": priority,
        "selected_assignee": assignee,
        "search": search,
        "ordering": ordering,
        "issue_statuses": Issue.STATUS_CHOICES,
        "issue_priorities": Issue.PRIORITY_CHOICES,
    })


@login_required
def issue_create(request, project_id):
    project = get_object_or_404(Project.objects.select_related("owner"), pk=project_id)
    if not project.user_can_access(request.user):
        messages.error(request, "You do not have access to that project.")
        return redirect("project_list")
    if request.method == "POST":
        form = IssueForm(
            request.POST,
            project=project,
            user=request.user,
            can_assign=project.user_can_manage_project(request.user),
        )
        if form.is_valid():
            issue = form.save(commit=False)
            issue.project = project
            issue.reporter = request.user
            issue.save()
            messages.success(request, "Issue created successfully.")
            return redirect("issue_detail", pk=issue.pk)
    else:
        form = IssueForm(
            project=project,
            user=request.user,
            can_assign=project.user_can_manage_project(request.user),
        )
    return render(request, "issues/issue_form.html", {"form": form, "project": project, "title": "Create issue"})


@login_required
def issue_detail(request, pk):
    issue = get_object_or_404(Issue.objects.select_related("project", "project__owner", "reporter", "assignee"), pk=pk)
    if not issue.user_can_access(request.user):
        messages.error(request, "You do not have access to that issue.")
        return redirect("issue_list")
    comments = issue.comments.select_related("author").all()
    form = CommentForm()
    return render(request, "issues/issue_detail.html", {
        "issue": issue,
        "comments": comments,
        "form": form,
        "can_edit_issue": issue.user_can_edit(request.user),
        "can_delete_issue": issue.user_can_delete(request.user),
        "can_manage_comments": issue.project.user_can_manage_project(request.user),
    })


@login_required
def issue_update(request, pk):
    issue = get_object_or_404(Issue.objects.select_related("project", "project__owner"), pk=pk)
    if not issue.user_can_access(request.user):
        messages.error(request, "You do not have access to that issue.")
        return redirect("issue_list")
    if not issue.user_can_edit(request.user):
        messages.error(request, "You do not have permission to edit this issue.")
        return redirect("issue_detail", pk=issue.pk)
    if request.method == "POST":
        form = IssueForm(
            request.POST,
            instance=issue,
            project=issue.project,
            user=request.user,
            can_assign=issue.project.user_can_manage_project(request.user),
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Issue updated.")
            return redirect("issue_detail", pk=issue.pk)
    else:
        form = IssueForm(
            instance=issue,
            project=issue.project,
            user=request.user,
            can_assign=issue.project.user_can_manage_project(request.user),
        )
    return render(request, "issues/issue_form.html", {"form": form, "project": issue.project, "title": "Edit issue", "issue": issue})


@login_required
def issue_delete(request, pk):
    issue = get_object_or_404(Issue.objects.select_related("project"), pk=pk)
    if not issue.user_can_access(request.user):
        messages.error(request, "You do not have access to that issue.")
        return redirect("issue_list")
    if not issue.user_can_delete(request.user):
        messages.error(request, "You do not have permission to delete this issue.")
        return redirect("issue_detail", pk=issue.pk)
    if request.method == "POST":
        project = issue.project
        issue.delete()
        messages.success(request, "Issue deleted.")
        return redirect("project_detail", pk=project.pk)
    return render(request, "issues/issue_confirm_delete.html", {"issue": issue})


@login_required
def issue_comments(request, pk):
    issue = get_object_or_404(Issue.objects.select_related("project"), pk=pk)
    if not issue.user_can_access(request.user):
        messages.error(request, "You do not have access to that issue.")
        return redirect("issue_list")
    comments = issue.comments.select_related("author").all()
    return render(request, "issues/issue_detail.html", {"issue": issue, "comments": comments})


@login_required
def add_comment(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if not issue.user_can_access(request.user):
        messages.error(request, "You cannot comment on inaccessible issues.")
        return redirect("issue_list")
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.issue = issue
            comment.author = request.user
            comment.save()
            messages.success(request, "Comment added.")
            return redirect("issue_detail", pk=issue.pk)
    return redirect("issue_detail", pk=issue.pk)


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("issue", "issue__project", "author"), pk=comment_id)
    if not comment.user_can_access(request.user):
        messages.error(request, "You cannot access this comment.")
        return redirect("issue_list")
    if not comment.user_can_edit(request.user):
        messages.error(request, "You cannot delete someone else's comment.")
        return redirect("issue_detail", pk=comment.issue.pk)
    comment.delete()
    messages.success(request, "Comment deleted.")
    return redirect("issue_detail", pk=comment.issue.pk)
