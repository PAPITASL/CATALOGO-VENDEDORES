from django import forms
from django.core.exceptions import ValidationError

from .models import Categoria, Marca, ModeloVehiculo, Producto


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ('nombre', 'logo', 'activo')

    def clean_nombre(self):
        return self.cleaned_data['nombre'].strip().upper()


class ModeloVehiculoForm(forms.ModelForm):
    class Meta:
        model = ModeloVehiculo
        fields = ('marca', 'nombre', 'activo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['marca'].queryset = Marca.objects.filter(activo=True).order_by('nombre')

    def clean_nombre(self):
        return self.cleaned_data['nombre'].strip().upper()


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ('nombre', 'descripcion', 'activo')

    def clean_nombre(self):
        return self.cleaned_data['nombre'].strip().upper()

    def clean_descripcion(self):
        return self.cleaned_data['descripcion'].strip().upper()


class ProductoForm(forms.ModelForm):
    marca_nombre = forms.CharField(
        label='Marca',
        max_length=100,
        help_text='Escribe una marca nueva o una existente; se reutilizará automáticamente.',
    )
    modelo_nombre = forms.CharField(
        label='Modelo',
        max_length=150,
        help_text='Se crea dentro de la marca indicada si todavía no existe.',
    )
    categoria_nombre = forms.CharField(
        label='Categoría',
        max_length=100,
        required=False,
        help_text='Opcional. También se crea o reutiliza por nombre.',
    )

    class Meta:
        model = Producto
        fields = (
            'sku',
            'nombre_pieza',
            'anio_inicio',
            'anio_fin',
            'imagen_principal',
            'precio_minimo',
            'precio_venta',
            'observaciones',
            'activo',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            'sku', 'nombre_pieza', 'marca_nombre', 'modelo_nombre', 'categoria_nombre',
            'anio_inicio', 'anio_fin', 'imagen_principal', 'precio_minimo',
            'precio_venta', 'observaciones', 'activo',
        ])
        self.fields['imagen_principal'].widget.attrs.update({'accept': 'image/*'})
        self.fields['marca_nombre'].widget.attrs.update({'placeholder': 'Ej. Toyota'})
        self.fields['modelo_nombre'].widget.attrs.update({'placeholder': 'Ej. Corolla'})
        self.fields['categoria_nombre'].widget.attrs.update({'placeholder': 'Ej. Farolas'})
        if self.instance and self.instance.pk:
            self.fields['marca_nombre'].initial = self.instance.modelo.marca.nombre
            self.fields['modelo_nombre'].initial = self.instance.modelo.nombre
            self.fields['categoria_nombre'].initial = self.instance.categoria.nombre if self.instance.categoria else ''

    def clean(self):
        cleaned_data = super().clean()
        anio_inicio = cleaned_data.get('anio_inicio')
        anio_fin = cleaned_data.get('anio_fin')
        costo = cleaned_data.get('costo')
        precio_minimo = cleaned_data.get('precio_minimo')
        precio_venta = cleaned_data.get('precio_venta')
        for field_name in ('sku', 'nombre_pieza', 'observaciones', 'marca_nombre', 'modelo_nombre', 'categoria_nombre'):
            value = cleaned_data.get(field_name)
            if isinstance(value, str):
                cleaned_data[field_name] = value.strip().upper()
        if not cleaned_data.get('marca_nombre', '').strip():
            self.add_error('marca_nombre', 'Escribe una marca.')
        if not cleaned_data.get('modelo_nombre', '').strip():
            self.add_error('modelo_nombre', 'Escribe un modelo.')

        if anio_inicio is not None and anio_fin is not None and anio_fin < anio_inicio:
            raise ValidationError('El año final no puede ser menor que el año inicial.')
        if costo is not None and costo < 0:
            self.add_error('costo', 'El costo no puede ser negativo.')
        if costo is not None and precio_minimo is not None and precio_minimo < costo:
            self.add_error('precio_minimo', 'El precio mínimo no puede ser menor que el costo.')
        if precio_minimo is not None and precio_venta is not None and precio_venta < precio_minimo:
            self.add_error('precio_venta', 'El precio de venta no puede ser menor que el precio mínimo.')
        return cleaned_data

    @staticmethod
    def _get_or_create_by_name(model, name, defaults=None):
        name = name.strip().upper()
        instance = model.objects.filter(nombre__iexact=name).first()
        if instance:
            return instance
        return model.objects.create(nombre=name, **(defaults or {}))

    def save(self, commit=True):
        marca = self._get_or_create_by_name(Marca, self.cleaned_data['marca_nombre'])
        modelo_nombre = self.cleaned_data['modelo_nombre'].strip().upper()
        modelo = ModeloVehiculo.objects.filter(marca=marca, nombre__iexact=modelo_nombre).first()
        if modelo is None:
            modelo = ModeloVehiculo.objects.create(marca=marca, nombre=modelo_nombre)

        categoria_nombre = self.cleaned_data.get('categoria_nombre', '').strip().upper()
        categoria = None
        if categoria_nombre:
            categoria = self._get_or_create_by_name(Categoria, categoria_nombre)

        self.instance.modelo = modelo
        self.instance.categoria = categoria
        return super().save(commit=commit)
