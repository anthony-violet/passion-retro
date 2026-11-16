from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm

from .models import User

class UserRegistrationForm(forms.Form):
    username = forms.CharField(
        label='', 
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-group', 'placeholder': 'Pseudo'})
    )
    email = forms.EmailField(
        label='',
        widget=forms.EmailInput(attrs={'class': 'form-group', 'placeholder': 'Email'})
    )
    password1 = forms.CharField(
        label='',
        widget=forms.PasswordInput(attrs={'class': 'form-group', 'placeholder': 'Mot de passe'})
    )
    password2 = forms.CharField(
        label='',
        widget=forms.PasswordInput(attrs={'class': 'form-group', 'placeholder': 'Mot de passe (vérification)'})
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match")

class UserLoginForm(forms.Form):
    username = forms.CharField(
        label='', 
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-group', 'placeholder': 'Pseudo'})
    )
    password = forms.CharField(
        label='',
        widget=forms.PasswordInput(attrs={'class': 'form-group', 'placeholder': 'Mot de passe'})
    )

class UserUpdateForm(forms.ModelForm):
    theme = forms.ChoiceField(
        label='Thème',
        choices=[
            ('default', 'Thème par défaut'),
            ('80s', 'Thème années 80'),
            ('00s', 'Thème années 2000'),
        ],
        widget=forms.Select(),
    )

    class Meta:
        model = User
        fields = [
            'avatar', 'first_name', 'last_name', 
            'favorite_console', 'favorite_game', 'favorite_game_genre',
            'anecdote',
            'biography', 'theme',
            'email', 'show_email',
            'website', 'twitter', 'discord', 'youtube',
        ]
        labels = {
            'avatar': 'Avatar',
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'biography': 'Biographie',
            'theme': 'Thème',
            'email': 'Adresse e-mail',
            'show_email': 'Afficher mon e-mail sur mon profil',
            'website': 'Site web',
            'twitter': 'Twitter / X (pseudo)',
            'discord': 'Discord (pseudo)',
            'youtube': 'YouTube (chaîne)',
            'favorite_console': 'Console(s) favorite(s)',
            'favorite_game': 'Jeu(x) favori(s)',
            'favorite_game_genre': 'Genre(s) favori(s)',
            'anecdote': 'Une anecdote à raconter ?'
        }
        widgets = {
            'biography': forms.Textarea(attrs={'rows': 5}),
            'favorite_console': forms.TextInput(attrs={'placeholder': 'SNES, MegaDrive, etc'}),
            'favorite_game': forms.TextInput(attrs={'placeholder': 'Le jeu qui a changé ta vie ?'}),
            'favorite_game_genre': forms.TextInput(attrs={'placeholder': 'RPG, Action, Sport, etc'}),
            'anecdote': forms.Textarea(attrs={'rows': 5}),
            'website': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'twitter': forms.TextInput(attrs={'placeholder': '@pseudo'}),
            'discord': forms.TextInput(attrs={'placeholder': 'pseudo#0000'}),
            'youtube': forms.TextInput(attrs={'placeholder': 'Nom de la chaîne ou URL'}),
        }


class PasswordUpdateForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Mot de passe actuel'
        self.fields['new_password1'].label = 'Nouveau mot de passe'
        self.fields['new_password2'].label = 'Confirmation du nouveau mot de passe'
        self.fields['new_password1'].help_text = None

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar', 'biography']

class CompleteProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar', 'birth_date', 'biography']

class PostForm(forms.Form):
    title = forms.CharField(
        max_length=150, 
        label='', 
        widget=forms.TextInput(attrs={'placeholder': 'Titre de l\'article'})
    )
    content = forms.CharField(
        label='', 
        widget=forms.Textarea(attrs={'placeholder': 'Contenu de l\'article'})
    )
