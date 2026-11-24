from django import template


register = template.Library()


@register.simple_tag
def metric_value(metric, field, suffix=""):
    """优先显示采集端上传的文字；空值显示 NaN，而不是误导性的 0。"""
    if metric is None:
        return "NaN"
    display_values = getattr(metric, "metric_display_values", None) or {}
    if field in display_values:
        return str(display_values[field])
    value = getattr(metric, field, None)
    if value is None:
        return "NaN"
    return f"{value}{suffix}"
