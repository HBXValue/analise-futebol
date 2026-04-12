from functools import wraps

from django.shortcuts import redirect

from valuation.models import User


SESSION_KEY = "valuation_user_id"


def get_current_user(request):
    user_id = request.session.get(SESSION_KEY)
    if not user_id:
        return None
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        request.session.pop(SESSION_KEY, None)
        return None


def login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not get_current_user(request):
            return redirect("login")
        return view_func(request, *args, **kwargs)

    return wrapped
