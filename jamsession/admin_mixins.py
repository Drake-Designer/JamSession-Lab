"""
Admin mixins shared across JamSession Lab apps.

django-admin-sortable2 is not officially supported by django-unfold. This mixin
patches the pagination action form so the bulk-action controls render correctly
in the Unfold changelist while keeping drag-and-drop sorting.
"""

from adminsortable2.admin import SortableAdminMixin
from django.forms import IntegerField
from unfold.forms import ActionForm
from unfold.widgets import UnfoldAdminIntegerFieldWidget


class UnfoldMovePageActionForm(ActionForm):
    step = IntegerField(
        required=False,
        initial=1,
        widget=UnfoldAdminIntegerFieldWidget(attrs={"id": "changelist-form-step"}),
        label=False,
    )
    page = IntegerField(
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(attrs={"id": "changelist-form-page"}),
        label=False,
    )


class UnfoldSortableAdminMixin(SortableAdminMixin):
    action_form = UnfoldMovePageActionForm
