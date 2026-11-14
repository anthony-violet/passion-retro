from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from .models import *
from users.leveling import grant_experience
from .forms import *

@login_required
def home(request):
    quizes = Quiz.objects.filter(is_active=True).select_related(
        'author'
    ).prefetch_related('author__levels')
    my_quizes = Quiz.objects.filter(author=request.user)

    if request.user.is_superuser:
        quizes = Quiz.objects.all().select_related(
            'author'
        ).prefetch_related('author__levels')
    
    
    # Récupérer les meilleurs scores de l'utilisateur pour chaque quiz
    user_scores = {}
    if request.user.is_authenticated:
        user_quiz_scores = UserQuiz.objects.filter(
            user=request.user
        ).values('quiz_id').annotate(
            best_score=Max('score')
        )
        user_scores = {score['quiz_id']: score['best_score'] for score in user_quiz_scores}
    
    return render(request, "games/quiz/home.html", {
        "quizes": quizes, 
        "my_quizes": my_quizes,
        "user_scores": user_scores
    })

@login_required
def quiz(request, quiz_id):
    quiz = get_object_or_404(
        Quiz.objects.select_related('author').prefetch_related('author__levels'),
        id=quiz_id,
    )
    
    if request.method == 'POST':
        # Vérifier si l'utilisateur a déjà participé à ce quiz
        user_quiz = UserQuiz.objects.filter(user=request.user, quiz=quiz).first()
        if user_quiz:
            # Si oui, supprimer les anciennes réponses
            UserAnswer.objects.filter(user_quiz=user_quiz).delete()
        else:
            # Si non, créer une nouvelle entrée
            user_quiz = UserQuiz.objects.create(user=request.user, quiz=quiz)

        score = 0
        for question in quiz.questions.all():
            choice_id = request.POST.get(f'question_{question.id}')
            if choice_id:
                choice = Choice.objects.get(id=choice_id)
                UserAnswer.objects.create(
                    user_quiz=user_quiz,
                    question=question,
                    choice=choice
                )
                if choice.is_correct:
                    score += 1
        
        user_quiz.score = score
        user_quiz.save()
        return redirect('quiz_result', user_quiz_id=user_quiz.id)

    return render(request, "games/quiz/quiz.html", {
        "quiz": quiz,
        "questions": quiz.questions.all()
    })

@login_required
def result(request, user_quiz_id):
    user_quiz = get_object_or_404(
        UserQuiz.objects.select_related('quiz', 'user').prefetch_related(
            'quiz__author__levels', 'user__levels'
        ),
        id=user_quiz_id,
        user=request.user,
    )
    total_questions = user_quiz.quiz.questions.count()

    # Chaque tentative de quiz n'est récompensée qu'une seule fois,
    # sinon recharger la page de résultat permettrait de farmer de l'XP.
    if not user_quiz.rewarded:
        grant_experience(request.user, 10 * user_quiz.score)
        user_quiz.rewarded = True
        user_quiz.save(update_fields=['rewarded'])

    attempts = UserQuiz.objects.filter(
        quiz=user_quiz.quiz
    ).select_related('user').prefetch_related('user__levels').order_by(
        'user_id', '-score'
    )
    best_attempts = {}
    for attempt in attempts:
        best_attempts.setdefault(attempt.user_id, attempt)

    sorted_attempts = sorted(
        best_attempts.values(),
        key=lambda attempt: (-attempt.score, attempt.user.username),
    )
    quiz_ranking = []
    previous_score = None
    current_rank = 0
    user_rank = None
    for position, attempt in enumerate(sorted_attempts, start=1):
        if attempt.score != previous_score:
            current_rank = position
            previous_score = attempt.score
        quiz_ranking.append({
            'rank': current_rank,
            'user': attempt.user,
            'score': attempt.score,
        })
        if attempt.user_id == request.user.id:
            user_rank = current_rank

    return render(request, "games/quiz/result.html", {
        "user_quiz": user_quiz,
        "total_questions": total_questions,
        "percentage": (user_quiz.score / total_questions) * 100 if total_questions > 0 else 0,
        "quiz_ranking": quiz_ranking[:10],
        "user_rank": user_rank,
        "total_players": len(quiz_ranking),
    })

@login_required
def create_quiz(request):
    form = QuizForm()
    if request.method == 'POST':
        quiz = Quiz.objects.create(author=request.user, name=request.POST.get('name'), description=request.POST.get('description'), is_active=False)
        return redirect('create_responses_quiz', quiz_id=quiz.id)
    
    return render(request, "games/quiz/create_quiz.html", {"form": form})

@login_required
def create_responses_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, author=request.user)
    questions = quiz.questions.all()
    choices = []
    for question in questions:
        choices.append(question.choices.all())
    
    form = QuestionForm()
    
    if request.method == 'POST':
        # Parcourir les données POST pour trouver les questions et réponses
        for key in request.POST:
            if key.startswith('ask-'):
                question_text = request.POST[key]
                if question_text:  # Vérifie si la question n'est pas vide
                    # Créer la question
                    question = Question.objects.create(
                        quiz=quiz,
                        question=question_text
                    )
                    
                    # Récupérer le numéro de la question depuis la clé
                    question_num = key.split('-')[1]
                    
                    # Chercher toutes les réponses associées à cette question
                    response_prefix = f'response-{question_num}-'
                    correct_response_key = f'is_correct-{question_num}'
                    correct_response_value = request.POST.get(correct_response_key)

                    for response_key in request.POST:
                        if response_key.startswith(response_prefix):
                            response_text = request.POST[response_key]
                            if response_text:  # Vérifie si la réponse n'est pas vide
                                response_num = response_key.split('-')[-1]
                                is_correct = (response_num == correct_response_value)
                                Choice.objects.create(
                                    question=question,
                                    choice=response_text,
                                    is_correct=is_correct  # Par défaut, aucune réponse n'est correcte
                                )
        
        return redirect('create_responses_quiz', quiz.id)  # Redirection vers la page d'accueil
    
    return render(request, "games/quiz/create_responses_quiz.html", {"form": form, "quiz": quiz})