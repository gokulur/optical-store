# adminpanel/templatetags/dict_filters.py
# Replace your existing file with this one — adds split() to your existing filters

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Usage: {{ my_dict|get_item:key_variable }}"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


@register.filter(name='split')
def split_filter(value, arg):
    """
    Split a string by delimiter.
    Usage: "a,b,c"|split:","
    """
    if value:
        return str(value).split(arg)
    return []