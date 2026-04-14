from django.shortcuts import render
from django.views.decorators.http import require_safe


@require_safe
def home(request):
    return render(request, 'home.html')