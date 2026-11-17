from django import forms
from .models import Post

class CreatePost(forms.Form):
    title = forms.CharField(
        max_length=150, 
        label='', 
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Titre du post'})
    )

    content = forms.CharField(
        label='', 
        required=True,
        widget=forms.Textarea(attrs={'placeholder': 'Contenu du post'})
    )

    active = forms.BooleanField(
        required=True, 
        label='Actif',
        initial=True
    )

class EditPost(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Titre du post'}),
            'content': forms.Textarea(attrs={'placeholder': 'Contenu du post'}),
        }

class ContributionForm(forms.Form):
    """Formulaire de contribution d'un article (ou de l'introduction d'un dossier)."""

    category = forms.TypedChoiceField(
        label='Rubrique',
        coerce=int,
        error_messages={'required': 'Choisis la rubrique dans laquelle ton article sera rangé.'},
    )
    title = forms.CharField(
        max_length=150,
        label='Titre',
        widget=forms.TextInput(attrs={'placeholder': 'Ex. : La Game Boy, la console qui a conquis les cours de récré'}),
    )
    content = forms.CharField(
        label='Contenu',
        widget=forms.Textarea(attrs={'rows': 14, 'placeholder': 'Raconte-nous tout… (BBCode accepté)'}),
    )

    def __init__(self, *args, with_category=True, **kwargs):
        super().__init__(*args, **kwargs)
        from .utils import contribution_categories

        self.category_choices = contribution_categories()
        if with_category:
            self.fields['category'].choices = [('', '— Choisir une rubrique —')] + [
                (cat.id, label) for cat, label in self.category_choices
            ]
        else:
            del self.fields['category']

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError('Le titre est obligatoire.')
        return title


def parse_chapters(data):
    """Récupère les chapitres d'un dossier envoyés par le formulaire.

    Retourne (chapitres, erreurs) où chapitres est une liste de dicts
    {'id', 'title', 'content'} dans l'ordre d'affichage.
    """
    ids = data.getlist('chapter_id')
    titles = data.getlist('chapter_title')
    contents = data.getlist('chapter_content')
    chapters, errors = [], []
    for index, (title, content) in enumerate(zip(titles, contents), start=1):
        title, content = title.strip(), content.strip()
        chapter_id = ids[index - 1] if index - 1 < len(ids) else ''
        if not title and not content:
            continue
        chapter = {'id': chapter_id, 'title': title, 'content': content, 'number': index}
        if not title or not content:
            chapter['error'] = 'Il manque le titre ou le contenu de ce chapitre.'
            errors.append(index)
        elif len(title) > 150:
            chapter['error'] = 'Le titre ne doit pas dépasser 150 caractères.'
            errors.append(index)
        chapters.append(chapter)
    return chapters, errors
