from django import forms
import datetime


class SearchForm(forms.Form):
    min_ingestion_date = forms.DateField(label='Od', required=True, initial='2017-01-01')
    max_ingestion_date = forms.DateField(label='Do', required=True, initial=datetime.date.today)
    satellite = forms.ChoiceField(widget=forms.RadioSelect, choices=(('S1', 'S1'), ('S2', 'S2')), label='Satelita', required=True)

    orbit_direction = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                label='Kierunek orbity',
                                                choices=(('ASC', 'ASCENDING'), ('DESC', 'DESCENDING')),
                                                required=False)
    polarisation_mode = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                label='Polaryzacja',
                                                choices=(('HH', 'HH'), ('HV', 'HV'), ('VH', 'VH'), ('VV', 'VV')),
                                                required=False)
    product_type = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                  label='Typ produktu',
                                                  choices=(('GRD', 'GRD'), ('SLC', 'SLC'), ('RAW', 'RAW'), ('any', 'dowolny')),
                                             required=False)
    sensor_mode = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                             label='Tryb sensora',
                                             choices=(
                                             ('IW', 'IW'), ('SM', 'SM'), ('EW', 'EW'), ('any', 'dowolny')),
                                            required=False)
    relative_orbit_number = forms.IntegerField(label='Względny numer orbity', required=False)

