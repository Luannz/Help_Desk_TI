# ==================== FORMS.PY ====================
from django import forms
from django.forms import ClearableFileInput
from .models import Chamado, Setor, Equipamento, Usuario
from django.contrib.auth.forms import UserCreationForm

class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True

# formulario pra CRIAR um usuario
class RegistroUsuarioForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Obrigatório. Informe um endereço de e-mail válido.')

    class Meta:
        model = Usuario
        fields = ['username', 'email', 'setor']
        labels = {
            'setor': 'Setor / Departamento',
        }
        widgets = {
            'setor': forms.Select(attrs={'class': 'form-select'}),  # Estilização do dropdown
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 1. Torna o campo obrigatório no formulário (Garante validação Python no Backend)
        self.fields['setor'].required = True
        
        # 2. Define o texto inicial neutro
        self.fields['setor'].empty_label = "Selecione um setor..."

# formulario para o PROPRIO usuario editar seu perfil
class EditarPerfilForm(forms.ModelForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = Usuario
        fields = ['username', 'email']


class ChamadoForm(forms.ModelForm):

    class Meta:
        model = Chamado
        fields = ['tipo', 'equipamento', 'subcategoria_duvida', 'descricao', 'prioridade']
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_tipo'
            }),
            'equipamento': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_equipamento'
            }),
            'subcategoria_duvida': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Excel, e-mail, impressora...',
                'id': 'id_subcategoria_duvida'
            }),
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Descreva o problema com detalhes...'
            }),
            'prioridade': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Começa vazio — o JS popula via fetch conforme o setor escolhido
        self.fields['equipamento'].queryset = Equipamento.objects.none()
        self.fields['equipamento'].required = False

        if 'equipamento' in self.fields:
            self.fields['equipamento'].label_from_instance = lambda obj: f"{obj.nome}"

        # Se for edição de chamado já salvo, carrega o equipamento atual
        if self.instance.pk and self.instance.equipamento:
            self.fields['equipamento'].queryset = Equipamento.objects.filter(
                pk=self.instance.equipamento.pk
            )

        # Chamado concluído: trava tudo
        if self.instance.pk and self.instance.status == 'concluido':
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        equipamento = cleaned_data.get('equipamento')

        if tipo == 'equipamento' and not equipamento:
            self.add_error('equipamento', 'Selecione o equipamento.')

        return cleaned_data


class SetorForm(forms.ModelForm):
    # Campo que recebe os IDs vindos do campo hidden do JS (ex: "1,4,7")
    equipamentos_ids = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Setor
        fields = ['nome', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={
                'placeholder': 'Ex: Financeiro, TI, RH...'
            }),
            'descricao': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Observações sobre o setor...'
            }),
        }

    def save(self, commit=True):
        setor = super().save(commit=commit)
        if commit:
            # Lê os IDs do campo hidden e atualiza o M2M
            ids_raw = self.cleaned_data.get('equipamentos_ids', '')
            if ids_raw:
                ids = [int(i) for i in ids_raw.split(',') if i.strip().isdigit()]
                setor.equipamentos.set(ids)
            else:
                setor.equipamentos.clear()
        return setor

class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = ['nome', 'categoria']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
        }