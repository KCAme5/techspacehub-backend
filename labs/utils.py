def filter_labs_by_plan(queryset, plan):
    if plan == "FREE":
        return queryset.filter(is_free=True, is_active=True)
    return queryset.filter(is_active=True)
