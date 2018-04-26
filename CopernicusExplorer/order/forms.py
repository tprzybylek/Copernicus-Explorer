from django import forms


class OrderForm(forms.Form):
    e_mail = forms.EmailField(label='E-Mail')
