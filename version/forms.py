from django import forms

from .models import HistoryVersion

MAX_IMAGE_SIZE = 5 * 1024 * 1024


class HistoryVersionForm(forms.ModelForm):
    remove_image = forms.BooleanField(required=False, label="Retirer la capture actuelle")

    class Meta:
        model = HistoryVersion
        fields = ['num_version', 'name', 'content', 'image']
        error_messages = {
            'num_version': {'required': 'Indique le numéro de version.'},
            'name': {'required': 'Donne un nom à la version.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].required = False
        self.fields['image'].widget = forms.FileInput(attrs={'accept': 'image/png,image/jpeg,image/gif,image/webp'})

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size') and image.size > MAX_IMAGE_SIZE:
            raise forms.ValidationError("La capture ne doit pas dépasser 5 Mo.")
        return image

    def save(self, commit=True):
        version = super().save(commit=False)
        # Retirer la capture ne supprime pas le fichier : il peut venir de la galerie.
        if self.cleaned_data.get('remove_image') and not self.files.get('image'):
            version.image = None
        if commit:
            version.save()
        return version
