from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProjectForm
from .models import Project, ProjectMembership


@login_required
def project_list(request):
    projects = Project.objects.prefetch_related("memberships")
    if not request.user.is_superuser:
        projects = projects.filter(Q(owner=request.user) | Q(memberships__user=request.user)).distinct()
    for project in projects:
        membership_roles = {
            membership.user_id: membership.role
            for membership in project.memberships.all()
        }
        role = ProjectMembership.OWNER if project.owner_id == request.user.id else membership_roles.get(request.user.id)
        project.can_edit_project = request.user.is_superuser or role in (ProjectMembership.OWNER, ProjectMembership.MANAGER)
    return render(request, "projects/project_list.html", {"projects": projects})


@login_required
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            ProjectMembership.objects.create(project=project, user=request.user, role=ProjectMembership.OWNER)
            messages.success(request, "Project created successfully.")
            return redirect("project_detail", pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, "projects/project_form.html", {"form": form, "title": "Create project"})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner").prefetch_related("memberships__user"), pk=pk)
    if not project.user_can_access(request.user):
        messages.error(request, "You do not have access to that project.")
        return redirect("project_list")
    issues = project.issues.select_related("reporter", "assignee", "project").all()
    return render(request, "projects/project_detail.html", {
        "project": project,
        "issues": issues,
        "can_edit_project": project.user_can_manage_project(request.user),
        "can_manage_members": project.user_can_manage_project(request.user),
        "can_delete_project": project.user_can_delete(request.user),
    })


@login_required
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_manage_project(request.user):
        messages.error(request, "You do not have permission to edit this project.")
        return redirect("project_detail", pk=project.pk)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated.")
            return redirect("project_detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, "projects/project_form.html", {"form": form, "title": "Edit project", "project": project})


@login_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_delete(request.user):
        messages.error(request, "Only the project owner can delete this project.")
        return redirect("project_detail", pk=project.pk)
    if request.method == "POST":
        project.delete()
        messages.success(request, "Project deleted.")
        return redirect("project_list")
    return render(request, "projects/project_confirm_delete.html", {"project": project})


@login_required
def project_members(request, pk):
    project = get_object_or_404(Project.objects.select_related("owner").prefetch_related("memberships__user"), pk=pk)
    if not project.user_can_access(request.user):
        messages.error(request, "You do not have access to that project.")
        return redirect("project_list")
    return render(request, "projects/project_members.html", {
        "project": project,
        "can_manage_members": project.user_can_manage_project(request.user),
    })


@login_required
@require_POST
def add_member(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_manage_project(request.user):
        messages.error(request, "You do not have permission to manage project members.")
        return redirect("project_members", pk=project.pk)
    username = request.POST.get("username", "").strip()
    if not username:
        messages.error(request, "Username is required.")
        return redirect("project_members", pk=project.pk)
    user = User.objects.filter(username=username).first()
    if not user:
        messages.error(request, "User not found.")
        return redirect("project_members", pk=project.pk)
    if user == project.owner:
        messages.error(request, "The project owner is already included.")
        return redirect("project_members", pk=project.pk)
    if ProjectMembership.objects.filter(project=project, user=user).exists():
        messages.error(request, "This user is already a member.")
        return redirect("project_members", pk=project.pk)
    role = request.POST.get("role", ProjectMembership.MEMBER)
    if role not in (ProjectMembership.MEMBER, ProjectMembership.MANAGER):
        messages.error(request, "Choose a valid member role.")
        return redirect("project_members", pk=project.pk)
    ProjectMembership.objects.create(project=project, user=user, role=role)
    messages.success(request, f"{user.username} was added to the project.")
    return redirect("project_members", pk=project.pk)


@login_required
@require_POST
def remove_member(request, pk, user_id):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_manage_project(request.user):
        messages.error(request, "You do not have permission to manage project members.")
        return redirect("project_members", pk=project.pk)
    membership = get_object_or_404(ProjectMembership, project=project, user_id=user_id)
    if membership.user == project.owner:
        messages.error(request, "The project owner cannot be removed.")
        return redirect("project_members", pk=project.pk)
    membership.delete()
    messages.success(request, "Member removed from project.")
    return redirect("project_members", pk=project.pk)


@login_required
@require_POST
def update_member_role(request, pk, user_id):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_manage_project(request.user):
        messages.error(request, "You do not have permission to manage project members.")
        return redirect("project_members", pk=project.pk)
    membership = get_object_or_404(ProjectMembership, project=project, user_id=user_id)
    if membership.user_id == project.owner_id:
        messages.error(request, "The project owner's role cannot be changed.")
        return redirect("project_members", pk=project.pk)
    role = request.POST.get("role")
    if role not in (ProjectMembership.MEMBER, ProjectMembership.MANAGER):
        messages.error(request, "Choose a valid member role.")
        return redirect("project_members", pk=project.pk)
    membership.role = role
    membership.save(update_fields=["role"])
    messages.success(request, f"{membership.user.username}'s role was updated.")
    return redirect("project_members", pk=project.pk)
