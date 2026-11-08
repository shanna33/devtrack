from django.urls import path

from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("new/", views.project_create, name="project_create"),
    path("<int:pk>/", views.project_detail, name="project_detail"),
    path("<int:pk>/edit/", views.project_update, name="project_update"),
    path("<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("<int:pk>/members/", views.project_members, name="project_members"),
    path("<int:pk>/members/add/", views.add_member, name="project_add_member"),
    path("<int:pk>/members/<int:user_id>/role/", views.update_member_role, name="project_update_member_role"),
    path("<int:pk>/members/<int:user_id>/remove/", views.remove_member, name="project_remove_member"),
]
