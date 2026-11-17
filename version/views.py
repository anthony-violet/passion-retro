from django.shortcuts import render

from .models import HistoryVersion


def version(request):
    return render(request, "version/version.html")


def history(request):
    versions = HistoryVersion.objects.all()
    return render(request, "version/history.html", {"versions": versions})
