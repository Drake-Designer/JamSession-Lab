from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import urlize
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlize_blank(value, autoescape=True):
    """
    Turn plain-text URLs into links that open in a new tab.

    Builds on Django's urlize (escapes HTML, adds nofollow), then adds
    target="_blank" plus noopener/noreferrer against tabnabbing.
    """
    linked = urlize(value, nofollow=True, autoescape=autoescape)
    linked = linked.replace("<a ", '<a target="_blank" ')
    linked = linked.replace(
        'rel="nofollow"', 'rel="nofollow noopener noreferrer"'
    )
    return mark_safe(linked)
