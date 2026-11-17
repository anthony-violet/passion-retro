from django import forms

ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png')
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGES_PER_UPLOAD = 20


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            if not data:
                return single_file_clean(None, initial)
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class AddImgGallery(forms.Form):
    image = MultipleFileField(
        label='Images',
        required=True,
        widget=MultipleFileInput(attrs={'class': 'form-inline', 'accept': '.jpg,.jpeg,.png'}),
        help_text=f'Vous pouvez sélectionner jusqu\'à {MAX_IMAGES_PER_UPLOAD} images (JPG, JPEG, PNG, 5 Mo max chacune).',
    )

    def clean_image(self):
        images = self.cleaned_data.get('image') or []
        if len(images) > MAX_IMAGES_PER_UPLOAD:
            raise forms.ValidationError(
                f'Vous ne pouvez pas importer plus de {MAX_IMAGES_PER_UPLOAD} images à la fois.'
            )
        errors = []
        for img in images:
            if not img.name.lower().endswith(ALLOWED_EXTENSIONS):
                errors.append(f'« {img.name} » : seuls les fichiers JPG, JPEG, PNG sont autorisés.')
            elif img.size > MAX_IMAGE_SIZE:
                errors.append(f'« {img.name} » : la taille de l\'image ne doit pas dépasser 5 Mo.')
        if errors:
            raise forms.ValidationError(errors)
        return images
