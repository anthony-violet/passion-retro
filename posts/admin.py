from django.contrib import admin
from django.db.models import QuerySet
from .models import Post, Category, NavSection

@admin.action(description="Activer les posts séléctionnés")
def activate_posts(modelAdmin, request, querySet: QuerySet):
    updated = querySet.update(active=True)
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
    fields = ('parent', 'post_parent', 'title', 'slug', 'category', 'content', 'type', 'image', 'author', 'active')
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