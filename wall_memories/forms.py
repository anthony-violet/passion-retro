from django import forms

from .models import Console, Memory, MemoryComment

MAX_IMAGE_SIZE = 5 * 1024 * 1024


class MemoryForm(forms.ModelForm):
    consoles = forms.ModelMultipleChoiceField(
        queryset=Console.objects.none(),
        required=False,
        label='La ou les consoles concernées',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'wm-console-choice'}),
    )
    era = forms.ChoiceField(
        choices=Memory.ERA_CHOICES,
        initial=Memory.ERA_90S,
        label="L'époque",
        widget=forms.RadioSelect(attrs={'class': 'wm-era'}),
    )

    class Meta:
        model = Memory
        fields = ['title', 'content', 'question', 'consoles', 'era', 'year', 'image']
        labels = {
            'title': 'Le titre de ton souvenir',
            'content': 'Ton histoire',
            'question': 'Une question pour la communauté (facultatif)',
            'year': "L'année (facultatif)",
            'image': 'Une photo (facultatif)',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': "Le jour où j'ai découvert Pokémon Rouge",
                'maxlength': 150,
            }),
            'content': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': "Un moment, une émotion, une anecdote... Fais-nous voyager dans le temps.",
            }),
            'question': forms.TextInput(attrs={
                'placeholder': 'Et toi, tu avais choisi quel starter ?',
                'maxlength': 200,
            }),
            'year': forms.NumberInput(attrs={'placeholder': 'ex : 1998', 'min': 1970, 'max': 2030}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['consoles'].queryset = Console.objects.filter(is_active=True)
        self.fields['image'].widget.attrs['accept'] = 'image/*'

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if len(title) < 3:
            raise forms.ValidationError('Le titre est un peu court.')
        return title

    def clean_content(self):
        content = self.cleaned_data['content'].strip()
        if len(content) < 20:
            raise forms.ValidationError('Raconte-nous en un peu plus (20 caractères minimum).')
        return content

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year is not None and not 1970 <= year <= 2030:
            raise forms.ValidationError('Année invalide.')
        return year

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size') and image.size > MAX_IMAGE_SIZE:
            raise forms.ValidationError("L'image ne doit pas dépasser 5 Mo.")
        return image


class MemoryCommentForm(forms.ModelForm):
    class Meta:
        model = MemoryComment
        fields = ['content']
        labels = {'content': ''}
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Toi aussi, tu as un souvenir à raconter ?',
            }),
        }

    def clean_content(self):
        content = self.cleaned_data['content'].strip()
        if len(content) < 2:
            raise forms.ValidationError('Ton commentaire est vide.')
        return content
