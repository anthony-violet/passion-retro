from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from panel.decorators import staff_required
from quiz.models import Quiz, Question, Choice


@staff_required
def quiz_list(request):
    quizzes = Quiz.objects.select_related('author').order_by('-created')
    return render(request, 'panel/quiz/list.html', {'quizzes': quizzes})


@staff_required
@require_POST
def quiz_toggle(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    quiz.is_active = not quiz.is_active
    quiz.save()
    messages.success(request, f"Quiz « {quiz.name} » {'activé' if quiz.is_active else 'désactivé'}.")
    return redirect('panel_quiz')


@staff_required
def quiz_delete(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if request.method == 'POST':
        name = quiz.name
        quiz.delete()
        messages.success(request, f"Quiz « {name} » supprimé.")
    return redirect('panel_quiz')


@staff_required
def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.prefetch_related('choices').all()
    return render(request, 'panel/quiz/detail.html', {'quiz': quiz, 'questions': questions})
