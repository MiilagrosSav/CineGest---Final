from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Template filter para buscar un valor en un diccionario o lista de tuplas.
    Uso: {{ dict|lookup:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, key)
    
    # Si es una lista de tuplas (como CHOICES)
    if isinstance(dictionary, (list, tuple)):
        for item_key, item_value in dictionary:
            if item_key == key:
                return item_value
    
    return key
