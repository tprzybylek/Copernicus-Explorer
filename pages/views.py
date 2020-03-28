from django.shortcuts import render

# Create your views here.

def pages_help(request):
    return render(request, 'pages/help.html')

def pages_about(request):
    return render(request, 'pages/about.html')