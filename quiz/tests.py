from django.test import TestCase
from quiz.models import Quiz, Question, Choice, UserQuiz, UserAnswer
from users.models import User

class QuizModelsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            active=True
        )
        
        self.quiz = Quiz.objects.create(
            author=self.user,
            name='Test Quiz',
            description='Description du quiz',
            is_active=True
        )
        
        self.question = Question.objects.create(
            quiz=self.quiz,
            question='Question de test ?'
        )
        
        self.correct_choice = Choice.objects.create(
            question=self.question,
            choice='Réponse correcte',
            is_correct=True
        )
        
        self.wrong_choice = Choice.objects.create(
            question=self.question,
            choice='Réponse incorrecte',
            is_correct=False
        )
    
    def test_create_quiz(self):
        self.assertEqual(self.quiz.name, 'Test Quiz')
        self.assertEqual(self.quiz.author, self.user)
        self.assertTrue(self.quiz.is_active)
    
    def test_create_question(self):
        self.assertEqual(self.question.question, 'Question de test ?')
        self.assertEqual(self.question.quiz, self.quiz)
    
    def test_create_choices(self):
        self.assertEqual(self.correct_choice.choice, 'Réponse correcte')
        self.assertTrue(self.correct_choice.is_correct)
        self.assertEqual(self.wrong_choice.choice, 'Réponse incorrecte')
        self.assertFalse(self.wrong_choice.is_correct)
    
    def test_quiz_string_representation(self):
        self.assertEqual(str(self.quiz), 'Test Quiz')
    
    def test_question_string_representation(self):
        self.assertEqual(str(self.question), 'Question de test ?')

class QuizUserTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            active=True
        )
        
        self.quiz = Quiz.objects.create(
            author=self.user,
            name='Test Quiz',
            description='Description du quiz',
            is_active=True
        )
        
        self.question = Question.objects.create(
            quiz=self.quiz,
            question='Question de test ?'
        )
        
        self.correct_choice = Choice.objects.create(
            question=self.question,
            choice='Réponse correcte',
            is_correct=True
        )
    
    def test_user_quiz_creation(self):
        user_quiz = UserQuiz.objects.create(
            user=self.user,
            quiz=self.quiz,
            score=5
        )
        
        self.assertEqual(user_quiz.user, self.user)
        self.assertEqual(user_quiz.quiz, self.quiz)
        self.assertEqual(user_quiz.score, 5)
    
    def test_user_answer_creation(self):
        # Note : UserAnswer nécessite un choice_id qui est NOT NULL
        # Pour ce test, on crée une réponse avec un choix
        user_quiz = UserQuiz.objects.create(
            user=self.user,
            quiz=self.quiz,
            score=0
        )
        
        user_answer = UserAnswer.objects.create(
            user_quiz=user_quiz,
            question=self.question,
            choice=self.correct_choice  # Ajout du choix requis
        )
        
        self.assertEqual(user_answer.user_quiz, user_quiz)
        self.assertEqual(user_answer.question, self.question)
        self.assertEqual(user_answer.choice, self.correct_choice)

class QuizBasicTest(TestCase):
    def test_quiz_app_exists(self):
        # Test basique pour vérifier que l'application quiz est installée
        from django.apps import apps
        self.assertTrue(apps.is_installed('quiz'))
    
    def test_quiz_models_exist(self):
        # Vérifier que les modèles principaux existent
        self.assertTrue(hasattr(Quiz, 'objects'))
        self.assertTrue(hasattr(Question, 'objects'))
        self.assertTrue(hasattr(Choice, 'objects'))
        self.assertTrue(hasattr(UserQuiz, 'objects'))
        self.assertTrue(hasattr(UserAnswer, 'objects'))
