from django import forms


class OrderForm(forms.Form):
    e_mail = forms.EmailField(label='E-Mail')
    layers = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                       label='Warstwy',
                                       choices=(('hh', 'HH'),
                                                ('hv', 'HV'),
                                                ('vh', 'VH'),
                                                ('vv', 'VV'),
                                                ('B02_10m', '10m B2'),
                                                ('B03_10m', '10m B3'),
                                                ('B04_10m', '10m B4'),
                                                ('B08_10m', '10m B8'),
                                                ('B05_20m', '20m B5'),
                                                ('B06_20m', '20m B6'),
                                                ('B07_20m', '20m B7'),
                                                ('B8A_20m', '20m B8a'),
                                                ('B11_20m', '20m B11'),
                                                ('B12_20m', '20m B12'),
                                                ('B01_60m', '60m B1'),
                                                ('B09_60m', '60m B9'),
                                                ('B10_60m', '60m B10')),
                                       required=False)
