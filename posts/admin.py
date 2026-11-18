from django.contrib import admin
from django.db.models import QuerySet
from .models import Post, Category, NavSection
from .news import publish_news

@admin.action(description="Activer les posts séléctionnés")
def activate_posts(modelAdmin, request, querySet: QuerySet):
    updated = querySet.update(active=True)
    for post in querySet.model.objects.filter(pk__in=querySet.values('pk'), type='news'):
        publish_news(post)
    modelAdmin.message_user(request, f"{updated} post(s) ont été activé(s).")

@admin.action(description="Désactiver les posts séléctionnés")
def deactivate_posts(modelAdmin, request, querySet: QuerySet):
    updated = querySet.update(active=False)
    modelAdmin.message_user(request, f"{updated} post(s) ont été désactivé(s).")

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'type', 'active', 'created', 'updated')
    list_filter = ('category', 'type', 'active', 'created', 'updated')
    search_fields = ('title', 'content', 'author__username')
    ordering = ('-created',)
    fields = ('parent', 'post_parent', 'title', 'slug', 'category', 'content', 'type', 'image', 'author', 'active',
              'excerpt', 'featured', 'published_at', 'image_alt', 'source_name', 'source_url', 'forum_prompt', 'topic')
    raw_id_fields = ('topic',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        publish_news(obj)
    prepopulated_fields = {'slug': ('title',)}
    actions = [activate_posts, deactivate_posts]

class NavSectionAdmin(admin.ModelAdmin):
    list_display = ('label', 'category', 'order', 'visible')
    list_editable = ('order', 'visible')
    list_filter = ('visible', 'category')
    search_fields = ('label',)
    ordering = ('order',)

admin.site.register(Post, PostAdmin)
admin.site.register(Category)
admin.site.register(NavSection, NavSectionAdmin)