from django.db import models
from users.models import User
from commons.bbcode_parser import BBCodeParser
from django.db.models.signals import pre_delete
from django.dispatch import receiver

class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Categorie'
        verbose_name_plural = 'Categories'

class NavSection(models.Model):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50, verbose_name='Libellé')
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='nav_sections',
        verbose_name="Catégorie d'articles",
        help_text="Les articles de cette catégorie apparaîtront dans la section.",
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    visible = models.BooleanField(default=True, verbose_name='Afficher dans la navbar')
    icon = models.CharField(max_length=50, blank=True, default='', verbose_name='Icône (emoji)')

    def __str__(self):
        return self.label

    class Meta:
        ordering = ['order', 'label']
        verbose_name = 'Section de navbar'
        verbose_name_plural = 'Sections de navbar'

class Post(models.Model):
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(max_length=200, unique=True, default='default-slug')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, default=1)
    title = models.CharField(max_length=200)
    content = models.TextField()
    type = models.CharField(max_length=200, default='news')
    image = models.ImageField(upload_to='images/', null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    contribution = models.BooleanField(default=False)
    forum_link = models.CharField(max_length=200, null=True, blank=True)
    post_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_posts')
    parent = models.BooleanField(default=True)
    draft = models.BooleanField(default=False)
    rejected = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True, default='')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Si le post a un parent, il ne doit pas être considéré comme parent
        # et il hérite toujours de la catégorie du dossier.
        if self.post_parent_id:
            self.parent = False
            self.category_id = self.post_parent.category_id
        else:
            self.parent = True
        super().save(*args, **kwargs)
        # Les articles d'un dossier suivent la catégorie du dossier.
        if self.parent and self.pk:
            Post.objects.filter(post_parent=self).exclude(
                category_id=self.category_id
            ).update(category_id=self.category_id)

    @property
    def is_pending(self):
        return not self.active and not self.rejected and not self.draft

    @property
    def nav_section(self):
        """Section visible de la navbar dans laquelle le dossier apparaît (ou None)."""
        return NavSection.objects.filter(category_id=self.category_id, visible=True).first()
    
    
    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
    
@receiver(pre_delete, sender=Post)
def handle_parent_deletion(sender, instance, **kwargs):
    # Si le post supprimé a des enfants
    for child in instance.child_posts.all():
        # Rendre l'enfant un parent
        child.post_parent = None
        child.parent = True
        child.save()