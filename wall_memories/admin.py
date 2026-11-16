from django.contrib import admin

from .models import Console, Memory, MemoryComment, MemoryFavorite, MemoryFeature, MemoryReaction


@admin.register(Console)
class ConsoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'manufacturer', 'release_year', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


class MemoryCommentInline(admin.TabularInline):
    model = MemoryComment
    extra = 0
    fields = ('author', 'content', 'status', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'era', 'status', 'reactions_count', 'comments_count', 'created_at')
    list_filter = ('status', 'era', 'consoles')
    search_fields = ('title', 'content', 'author__username')
    filter_horizontal = ('consoles',)
    inlines = [MemoryCommentInline]


@admin.register(MemoryComment)
class MemoryCommentAdmin(admin.ModelAdmin):
    list_display = ('memory', 'author', 'status', 'created_at')
    list_filter = ('status',)


admin.site.register(MemoryReaction)
admin.site.register(MemoryFavorite)
admin.site.register(MemoryFeature)
