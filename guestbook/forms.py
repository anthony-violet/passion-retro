from django import forms

from . import antispam


class CreateGuestbook(forms.Form):
    author = forms.CharField(
        max_length=50,
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Nom'})
    )
    content = forms.CharField(
        max_length=100,
        label='',
        widget=forms.Textarea(attrs={'placeholder': 'Message'})
    )
    # Champ piège : masqué aux humains, rempli par les robots.
    website = forms.CharField(
        required=False,
        label='Ne pas remplir ce champ',
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'tabindex': '-1'}),
    )
    form_token = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['form_token'] = antispam.make_form_token()

    @property
    def is_bot(self):
        """Champ piège rempli ou formulaire envoyé trop vite : sans doute un robot."""
        data = self.data
        return bool(data.get(antispam.HONEYPOT_FIELD)) or not antispam.form_token_is_valid(
            data.get(antispam.TIMESTAMP_FIELD)
        )

    def clean_content(self):
        content = self.cleaned_data['content'].strip()
        if antispam.contains_link(content):
            raise forms.ValidationError("Les liens ne sont pas autorisés dans le livre d'or.")
        if antispam.is_duplicate(content):
            raise forms.ValidationError("Ce message a déjà été publié.")
        return content
