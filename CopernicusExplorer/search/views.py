# Django
from django.shortcuts import render
from django.contrib.gis.geos import Polygon

# local
from .forms import SearchForm
from .models import Product
from order.cart import Cart

# Create your views here.


def search_form(request):
    form = SearchForm()
    return render(request, 'search/form.html', {'form': form})


def results(request):
    def get_queryset(f):
        r = Product.objects
        r = r.filter(ingestion_date__gte=f['min_ingestion_date'],
                     ingestion_date__lte=f['max_ingestion_date'],
                     satellite__startswith=f['satellite']
                     )

        if f['orbit_direction']:
            r = r.filter(orbit_direction__in=f['orbit_direction'])

        # TODO polarisation_mode
        if f['polarisation_mode']:
            r = r.filter(polarisation_mode__in=f['polarisation_mode'])

        if f['product_type']:
            r = r.filter(product_type__in=f['product_type'])

        if f['sensor_mode']:
            r = r.filter(sensor_mode__in=f['sensor_mode'])

        if f['relative_orbit_number'] is not None:
            r = r.filter(relative_orbit_number=f['relative_orbit_number'])

        if f['search_extent_min_x'] is not None:
            search_extent = Polygon.from_bbox((f['search_extent_min_x'],
                                               f['search_extent_min_y'],
                                               f['search_extent_max_x'],
                                               f['search_extent_max_y'])
                                              )

            r = r.filter(coordinates__intersects=search_extent)

        r_geom = []
        for result in r:
            r_tuple = result.coordinates.tuple[0]
            r_tuple_coords = []
            for point in r_tuple:
                r_tuple_coords.append([point[1], point[0]])
            r_geom.append("L.polygon("
                          + str(r_tuple_coords)
                          + ", {className: '"
                          + result.id
                          + "', color: '#000', "
                            "weight: '1', "
                            "fillOpacity: '0.1'"
                            "}).addTo(map);"
                          )
        return r, r_geom

    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            form_data = form.cleaned_data

            search_extent_js = None

            if form_data['search_extent_min_x'] is not None:
                search_extent = Polygon.from_bbox((form_data['search_extent_min_x'],
                                                   form_data['search_extent_min_y'],
                                                   form_data['search_extent_max_x'],
                                                   form_data['search_extent_max_y'])
                                                  )

                search_extent_js = 'L.geoJSON(' \
                                   + search_extent.geojson \
                                   + ', {style: ' \
                                     '{"color": "#000", ' \
                                     '"weight": 1, ' \
                                     '"fillOpacity": 0, ' \
                                     '"dashArray": "10, 5"}' \
                                     '}).addTo(map);'

                cart = Cart(request)
                cart.set_extent(search_extent.geojson)

            results, results_geom = get_queryset(form_data)
            return render(request, 'search/results.html',
                          context={'form': form.cleaned_data,
                                   'results': results,
                                   'results_geom': results_geom,
                                   'search_extent': search_extent_js})
