from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.gallery_list, name="list"),
    path("upload/", views.gallery_upload, name="upload"),
    path("my-uploads/", views.my_uploads, name="my_uploads"),
]
