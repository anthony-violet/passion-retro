from django.shortcuts import redirect
from functools import wraps

def staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper
