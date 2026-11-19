from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.password_validation import validate_password

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

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ce pseudo est déjà pris.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Les deux mots de passe ne correspondent pas.")
        elif password1:
            candidate = User(
                username=cleaned_data.get('username', ''),
                email=cleaned_data.get('email', ''),
            )
            try:
                validate_password(password1, candidate)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        return cleaned_data


class ResendActivationForm(forms.Form):
    email = forms.EmailField(
        label='',
        widget=forms.EmailInput(attrs={'class': 'form-group', 'placeholder': 'Ton adresse e-mail'}),
    )

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
    theme = forms.ChoiceField(label='Thème', choices=[], widget=forms.Select())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .themes import theme_options

        # Seuls les thèmes gratuits et ceux achetés en boutique sont proposés ;
        # on garde le thème actuel pour ne pas bloquer l'enregistrement du profil.
        current = getattr(self.instance, 'theme', None)
        choices = [(code, label) for code, label, locked in theme_options(self.instance)
                   if not locked or code == current]
        if current and current not in dict(choices):
            choices.append((current, current))
        self.fields['theme'].choices = choices

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
