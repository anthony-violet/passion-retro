from django import forms

SUBSCRIBE_LABEL = 'Recevoir un email à chaque nouvelle réponse'
SUBSCRIBE_HELP_TEXT = 'Vous pourrez vous désabonner à tout moment.'

class CreateTopic(forms.Form):
    TOPIC_TYPE_CHOICES = (
        ('normal', 'Normal'),
        ('announce', 'Annonce'),
    )
    title = forms.CharField(
        max_length=150, 
        label='', 
        widget=forms.TextInput(attrs={'placeholder': 'Titre du sujet'})
    )
    content = forms.CharField(
        label='', 
        widget=forms.Textarea(attrs={'placeholder': 'Contenu du sujet'})
    )
    type = forms.ChoiceField(choices=TOPIC_TYPE_CHOICES, label='Type de sujet')
    subscribe = forms.BooleanField(
        required=False,
        initial=True,
        label=SUBSCRIBE_LABEL,
        help_text=SUBSCRIBE_HELP_TEXT,
        widget=forms.CheckboxInput(attrs={'class': 'topic-subscribe-checkbox'}),
    )

class CreatePost(forms.Form):
    content = forms.CharField(
        label='', 
        widget=forms.Textarea(attrs={'placeholder': 'Contenu du message'})
    )
    subscribe = forms.BooleanField(
        required=False,
        initial=True,
        label=SUBSCRIBE_LABEL,
        help_text=SUBSCRIBE_HELP_TEXT,
        widget=forms.CheckboxInput(attrs={'class': 'topic-subscribe-checkbox'}),
    )

class EditPost(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Message")