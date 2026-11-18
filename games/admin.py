from django.contrib import admin
from .models import LittleBacCategories

admin.site.register(LittleBacCategories)
from .models import MysteryAttempt, MysteryClue, MysteryGame


class MysteryClueInline(admin.TabularInline):
    model = MysteryClue
    extra = 1


@admin.register(MysteryGame)
class MysteryGameAdmin(admin.ModelAdmin):
    list_display = ('publish_date', 'title', 'author')
    search_fields = ('title', 'aliases')
    inlines = [MysteryClueInline]


@admin.register(MysteryAttempt)
class MysteryAttemptAdmin(admin.ModelAdmin):
    list_display = ('game', 'user', 'status', 'clues_revealed', 'xp_earned', 'gold_earned')
    list_filter = ('status',)
