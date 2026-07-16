# ==================== ADMIN.PY ====================
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Setor, Equipamento, Chamado, ImagemChamado

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Informações Adicionais', {'fields': ('tipo', 'setor')}),
    )
    list_display = ['username', 'tipo']
    list_filter = ['tipo']


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'criado_em']
    search_fields = ['nome']


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'categoria']
    search_fields = ['nome']
    search_fields = ['categoria']


@admin.register(Chamado)
class ChamadoAdmin(admin.ModelAdmin):
    list_display = ['id', 'solicitante', 'status', 'tipo', 'prioridade', 'criado_em']
    list_filter = ['status', 'tipo', 'prioridade']
    search_fields = ['descricao']


@admin.register(ImagemChamado)
class ImagemChamadoAdmin(admin.ModelAdmin):
    list_display = ['id', 'chamado', 'descricao', 'enviado_em']
    list_filter = ['enviado_em']
