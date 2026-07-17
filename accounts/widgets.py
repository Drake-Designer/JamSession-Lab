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
        if self.is_initial(value):
            preview_url = web_image_url(
                value,
                width=200,
                height=200,
                crop="fill",
            )
        context["widget"]["preview_url"] = preview_url
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
        return context

    def render(self, name, value, attrs=None, renderer=None):
        """
        Render via the project template loader so we do not need to change
        FORM_RENDERER / django.forms for a single custom widget.
        """
        context = self.get_context(name, value, attrs)
        return mark_safe(render_to_string(self.template_name, context))
