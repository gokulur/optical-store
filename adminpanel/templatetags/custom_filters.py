# adminpanel/templatetags/dict_filters.py
# Create this file at: adminpanel/templatetags/dict_filters.py
# Also make sure adminpanel/templatetags/__init__.py exists (empty file)

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Usage: {{ my_dict|get_item:key_variable }}"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''