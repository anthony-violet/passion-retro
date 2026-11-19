from django.contrib import admin

from .models import Category, Item


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'is_active')
    list_editable = ('position', 'is_active')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'kind', 'rarity', 'price', 'discount_percent', 'stock', 'is_active')
    list_filter = ('kind', 'rarity', 'category', 'is_active')
    search_fields = ('name', 'css_class')
