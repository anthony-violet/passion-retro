from django.shortcuts import render
from .models import HistoryVersion

def version(request):
    return render(request, "version/version.html")

# Create your views here.
def history(request):
    datas = HistoryVersion.objects.all()
    return render(request, "version/history.html", {"datas": datas})