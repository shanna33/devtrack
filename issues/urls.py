from django.urls import path

from . import views

urlpatterns = [
    path("", views.issue_list, name="issue_list"),
    path("new/<int:project_id>/", views.issue_create, name="issue_create"),
    path("<int:pk>/", views.issue_detail, name="issue_detail"),
    path("<int:pk>/edit/", views.issue_update, name="issue_update"),
    path("<int:pk>/delete/", views.issue_delete, name="issue_delete"),
    path("<int:pk>/comments/", views.issue_comments, name="issue_comments"),
    path("<int:pk>/comments/add/", views.add_comment, name="add_comment"),
    path("comments/<int:comment_id>/delete/", views.delete_comment, name="delete_comment"),
]
