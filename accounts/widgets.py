from django.forms.widgets import ClearableFileInput
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from jamsession.cloudinary_delivery import web_image_url


class ProfilePictureInput(ClearableFileInput):
    """
    Clearable file input that shows a circular image preview instead of the
    raw Cloudinary "Currently: <url>" link from Django's default widget.
    """

    clear_checkbox_label = _("Remove")
    input_text = _("Change photo")
    initial_text = _("Current photo")
    template_name = "accounts/widgets/profile_picture_input.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        preview_url = ""
        focus_x = None
        focus_y = None
        if self.is_initial(value):
            # Scaled full image — crop is applied in CSS via object-position.
            preview_url = web_image_url(
                value,
                width=320,
                crop="limit",
                quality="auto",
            )
            instance = getattr(value, "instance", None)
            if instance is not None:
                focus_x = getattr(instance, "profile_picture_focus_x", 50)
                focus_y = getattr(instance, "profile_picture_focus_y", 50)
        context["widget"]["preview_url"] = preview_url
        context["widget"]["focus_x"] = focus_x
        context["widget"]["focus_y"] = focus_y
        # Pop so these are not dumped onto the <input type="file"> element.
        widget_attrs = context["widget"]["attrs"]
        context["widget"]["immediate_remove_url"] = widget_attrs.pop(
            "data-immediate-remove-url",
            "",
        )
        context["widget"]["immediate_upload_url"] = widget_attrs.pop(
            "data-immediate-upload-url",
            "",
        )
        context["widget"]["heic_preview_url"] = widget_attrs.pop(
            "data-heic-preview-url",
            "",
        )
        return context

    def render(self, name, value, attrs=None, renderer=None):
        """
        Render via the project template loader so we do not need to change
        FORM_RENDERER / django.forms for a single custom widget.
        """
        context = self.get_context(name, value, attrs)
        return mark_safe(render_to_string(self.template_name, context))
