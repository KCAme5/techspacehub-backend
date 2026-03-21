from builder.models import UserCredits

def get_or_create_credits(user):
    """
    Ensures a user has a UserCredits record with at least 20 free credits initially.
    Returns (credits_obj, created).
    """
    return UserCredits.objects.get_or_create(
        user=user,
        defaults={
            "credits": 20,
            "total_purchased": 0,
            "total_used": 0,
            "is_free_tier": True,
        },
    )
