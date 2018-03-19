from django.shortcuts import render
from .models import Product


# Create your views here.

from django.http import HttpResponseRedirect

from .forms import SearchForm

def search_form(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = SearchForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # ...
            # redirect to a new URL:
            return HttpResponseRedirect('/search/results/', {'form': form})

    else:
        form = SearchForm()

    return render(request, 'search/form.html', {'form': form})


def results(request):
    return render(request, 'search/results.html', {})
