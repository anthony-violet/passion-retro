from django.contrib import admin
from .models import HistoryVersion


class HistoryVersionAdmin(admin.ModelAdmin):
    list_display = ('num_version', 'name', 'created_at')
    search_fields = ('num_version', 'name', 'content', 'image')
    ordering = ('-created_at',)
    fields = ('num_version', 'name', 'content', 'image')


admin.site.register(HistoryVersion, HistoryVersionAdmin)
