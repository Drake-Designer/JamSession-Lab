from django.urls import path

from registrations import views as registration_views

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("manage/", views.event_manage, name="manage"),
    path("create/", views.event_create, name="create"),
    path("<int:pk>/", views.event_detail, name="detail"),
    path("<int:pk>/edit/", views.event_edit, name="edit"),
    path("<int:pk>/delete/", views.event_delete, name="delete"),
    path("<int:pk>/toggle-active/", views.event_toggle_active, name="toggle_active"),
    path(
        "<int:pk>/toggle-registrations/",
        views.event_toggle_registrations,
        name="toggle_registrations",
    ),
    path("<int:pk>/register/", registration_views.register, name="register"),
    path(
        "<int:pk>/register/edit/",
        registration_views.edit_registration,
        name="register_edit",
    ),
    path(
        "<int:pk>/register/confirmation/",
        registration_views.register_confirmation,
        name="register_confirmation",
    ),
    path("<int:pk>/cancel/", registration_views.cancel, name="cancel"),
    path("<int:pk>/attendees/", registration_views.staff_lists, name="attendees"),
]