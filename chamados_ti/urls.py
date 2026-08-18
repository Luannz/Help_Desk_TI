# ==================== URLS.PY ====================
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('solicitante/', views.solicitante_dashboard, name='solicitante_dashboard'),
    path('agente/', views.agente_dashboard, name='agente_dashboard'),
    path('registrar/', views.registrar_view, name='registrar'),
    path('perfil/editar/', views.editar_perfil_view, name='editar_perfil'),
    path('primeiro-acesso/', views.primeiro_acesso_senha_view, name='primeiro_acesso_senha'),

    #=================== SETORES ====================
    path('setores/', views.gerenciar_setores, name='gerenciar_setores'),
    path('setor/editar/<int:pk>/', views.editar_setor, name='editar_setor'),

    #=================== EQUIPAMENTOS ====================
    path('equipamentos/', views.gerenciar_equipamentos, name='gerenciar_equipamentos'),
    path('equipamento/editar/<int:pk>/', views.editar_equipamento, name='editar_equipamento'),

    #=================== CHAMADOS ====================
    path('chamado/criar', views.criar_chamado, name='criar_chamado'),
    path('chamado/<int:chamado_id>/status/', views.atualizar_status, name='atualizar_status'),
    path('chamados/<int:chamado_id>/adicionar-mensagem/', views.adicionar_mensagem_chamado, name='adicionar_mensagem_chamado'),

    #=================== HISTÓRICOS ====================
    path('historicos/', views.historicos, name='historicos'),
    path('historico/usuario/<int:usuario_id>/', views.historico_usuario, name='historico_usuario'),
    path('historico/chamado/<int:chamado_id>/', views.detalhe_chamado, name='detalhe_chamado'),
    #===================== ADMIN DASHBOARD ====================
    path('admin-agente/', views.dashboard_admin_agente, name='dashboard_admin_agente'),
    path('chamado/atribuir/<int:chamado_id>/', views.atribuir_chamado, name='atribuir_chamado'),

    #==================== Endpoint JSON para o JS ===================
    path('api/equipamentos/', views.api_equipamentos, name='api_equipamentos'),
    path('api/equipamentos-do-setor/<int:setor_id>/', views.api_equipamentos_do_setor, name='api_equipamentos_do_setor'),
    path('api/setor-do-usuario/<int:user_id>/',views.api_obter_setor_usuario, name='api_setor_usuario'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)