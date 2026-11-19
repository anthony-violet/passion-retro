from .models import Quiz

def pending_quizes_count(request):
    count = Quiz.objects.filter(is_active=False).count()
    return {'pending_quizes_count': count}