from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("post/new/", views.post_create, name="post_create"),
    path("post/<slug:slug>/", views.post_detail, name="post_detail"),
    path("post/<slug:slug>/edit/", views.post_edit, name="post_edit"),
    path("post/<slug:slug>/delete/", views.post_delete, name="post_delete"),
    path("post/<slug:slug>/like/", views.like_toggle, name="like_toggle"),
    path("post/<slug:slug>/comment/", views.comment_add, name="comment_add"),
    path("comment/<int:pk>/edit/", views.comment_edit, name="comment_edit"),
    path("comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("moderate/", views.moderation_queue, name="moderation_queue"),
    path(
        "moderate/post/<slug:slug>/approve/",
        views.moderation_post_approve,
        name="moderation_post_approve",
    ),
    path(
        "moderate/post/<slug:slug>/reject/",
        views.moderation_post_reject,
        name="moderation_post_reject",
    ),
    path(
        "moderate/post/<slug:slug>/delete/",
        views.moderation_post_delete,
        name="moderation_post_delete",
    ),
    path(
        "moderate/comment/<int:pk>/approve/",
        views.moderation_comment_approve,
        name="moderation_comment_approve",
    ),
    path(
        "moderate/comment/<int:pk>/reject/",
        views.moderation_comment_reject,
        name="moderation_comment_reject",
    ),
    path(
        "moderate/comment/<int:pk>/delete/",
        views.moderation_comment_delete,
        name="moderation_comment_delete",
    ),
    path(
        "moderate/gallery/<int:pk>/approve/",
        views.moderation_gallery_approve,
        name="moderation_gallery_approve",
    ),
    path(
        "moderate/gallery/<int:pk>/reject/",
        views.moderation_gallery_reject,
        name="moderation_gallery_reject",
    ),
    path(
        "moderate/gallery/<int:pk>/delete/",
        views.moderation_gallery_delete,
        name="moderation_gallery_delete",
    ),
    path("admin-tool/", views.admin_tool, name="admin_tool"),
    path(
        "admin-tool/post/<slug:slug>/preview/",
        views.admin_post_preview,
        name="admin_post_preview",
    ),
    path(
        "admin-tool/comment/<int:pk>/preview/",
        views.admin_comment_preview,
        name="admin_comment_preview",
    ),
    path(
        "admin-tool/gallery/<int:pk>/delete/",
        views.admin_tool_gallery_delete,
        name="admin_tool_gallery_delete",
    ),
    path(
        "admin-tool/gallery/<int:pk>/pin-order/",
        views.admin_tool_pin_order,
        name="admin_tool_pin_order",
    ),
    path(
        "admin-tool/post/<slug:slug>/delete/",
        views.admin_tool_post_delete,
        name="admin_tool_post_delete",
    ),
    path(
        "admin-tool/comment/<int:pk>/delete/",
        views.admin_tool_comment_delete,
        name="admin_tool_comment_delete",
    ),
    path(
        "admin-tool/bulk-delete/",
        views.admin_tool_bulk_delete,
        name="admin_tool_bulk_delete",
    ),
    path(
        "admin-tool/bulk-moderate/",
        views.admin_tool_bulk_moderate,
        name="admin_tool_bulk_moderate",
    ),
]
