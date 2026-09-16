from decimal import Decimal

from django import forms

from catalogo.models import Producto


class GenerarImagenForm(forms.Form):
    precio_publicacion = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0'),
        label='Precio para publicación',
    )

    def __init__(self, *args, producto, **kwargs):
        super().__init__(*args, **kwargs)
        self.producto = producto
        self.fields['precio_publicacion'].initial = producto.precio_venta

    def clean_precio_publicacion(self):
        precio = self.cleaned_data['precio_publicacion']
        if precio < self.producto.precio_minimo:
            raise forms.ValidationError(
                f'El precio debe ser igual o superior a ${self.producto.precio_minimo:,.0f}.'
            )
        return precio
