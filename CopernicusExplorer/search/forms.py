from django import forms
import datetime


class SearchForm(forms.Form):
    min_sensing_date = forms.DateField(label='Od',
                                       required=False)

    max_sensing_date = forms.DateField(label='Do',
                                       required=False)

    min_ingestion_date = forms.DateField(label='Od',
                                         required=True,
                                         initial=datetime.datetime.now() - datetime.timedelta(days=7))

    max_ingestion_date = forms.DateField(label='Do',
                                         required=True,
                                         initial=datetime.date.today)

    satellite = forms.ChoiceField(widget=forms.RadioSelect,
                                  choices=(('S1', 'S1'), ('S2', 'S2')),
                                  label='Satelita',
                                  required=True)

    orbit_direction = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                label='Kierunek orbity',
                                                choices=(('ASCENDING', 'ASCENDING'),
                                                         ('DESCENDING', 'DESCENDING')),
                                                required=False,)

    polarisation_mode = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                  label='Polaryzacja',
                                                  choices=(('HH', 'HH'),
                                                           ('HV', 'HV'),
                                                           ('VH', 'VH'),
                                                           ('VV', 'VV')),
                                                  required=False)

    product_type = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                             label='Typ produktu',
                                             choices=(('GRD', 'GRD'),
                                                      ('SLC', 'SLC'),
                                                      ('RAW', 'RAW'),
                                                      ('S2MSI2A', 'S2MSI2A'),
                                                      ('S2MSI1C', 'S2MSI1C')),
                                             required=False)

    sensor_mode = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                            label='Tryb sensora',
                                            choices=(('IW', 'IW'),
                                                     ('SM', 'SM'),
                                                     ('EW', 'EW'),
                                                     ('WV', 'WV')),
                                            required=False)

    cloud_cover = forms.DecimalField(label='Maksymalny % pokrywy chmur',
                                     required=False)

    relative_orbit_number = forms.IntegerField(label='Względny numer orbity',
                                               required=False)

    search_extent_min_x = forms.DecimalField(label='Minimalna długość geograficzna (λ)',
                                             required=False)

    search_extent_max_x = forms.DecimalField(label='Maksymalna długość geograficzna (λ)',
                                             required=False)

    search_extent_min_y = forms.DecimalField(label='Minimalna szerokość geograficzna (φ)',
                                             required=False)

    search_extent_max_y = forms.DecimalField(label='Maksymalna szerokość geograficzna (φ)',
                                             required=False)

    def clean(self):
        cleaned_data = super().clean()
        satellite = cleaned_data.get('satellite')

        product_type = set(cleaned_data.get('product_type'))
        cloud_cover = cleaned_data.get('cloud_cover')
        polarisation_mode = set(cleaned_data.get('polarisation_mode'))
        sensor_mode = set(cleaned_data.get('sensor_mode'))

        s1_product_type = {'GRD', 'SLC', 'RAW'}
        s2_product_type = {'S2MSI2A', 'S2MSI2A'}

        if satellite == 'S1' and (product_type.intersection(s2_product_type) or
                                  cloud_cover):
            raise forms.ValidationError("Wybrano satelitę S1 jednak otrzymano atrybuty S2")
        elif satellite == 'S2' and (product_type.intersection(s1_product_type)
                                    or polarisation_mode
                                    or sensor_mode):
            raise forms.ValidationError("Wybrano satelitę S2 jednak otrzymano atrybuty S1")
