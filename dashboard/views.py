from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from issues.models import Issue
from projects.models import Project


@login_required
def dashboard(request):
    projects = Project.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct()
    issues = Issue.objects.select_related("project", "assignee", "reporter").filter(project__in=projects)

    context = {
        "total_projects": projects.count(),
        "total_issues": issues.count(),
        "open_issues": issues.filter(status__in=[Issue.STATUS_TODO, Issue.STATUS_IN_PROGRESS, Issue.STATUS_IN_REVIEW]).count(),
        "completed_issues": issues.filter(status=Issue.STATUS_DONE).count(),
        "assigned_to_me": issues.filter(assignee=request.user).count(),
        "recent_issues": issues.order_by("-updated_at")[:5],
        "recent_projects": projects.order_by("-updated_at")[:5],
    }
    return render(request, "dashboard.html", context)
