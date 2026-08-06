# ==================== VIEWS.PY ====================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import Case, When, Value, IntegerField, Q , Max, F, Count
from .models import Usuario, Setor, Equipamento, Chamado, ImagemChamado, MensagemChamado
from .forms import ChamadoForm, SetorForm, EquipamentoForm, RegistroUsuarioForm, EditarPerfilForm
from datetime import datetime, timedelta
from django.views.decorators.http import require_POST
import os

from .utils import enviar_notificacao_email  # Importa a função de notificação

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Nome de usuário ou senha inválidos.')
    return render(request, 'chamados_ti/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def csrf_failure_view(request, reason=""):
    # Adiciona a mensagem que o usuário vai ler ao chegar no login
    messages.warning(request, "Sua sessão expirou por inatividade. Por favor, entre novamente.")
    
    # Redireciona para a página de login
    return redirect('login_view') # nome da URL de login

def registrar_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Como padrão, novos usuários criados sozinhos entram como 'solicitante'
            user.tipo = 'solicitante' 
            user.save()
            
            messages.success(request, 'Conta criada com sucesso! Você já pode fazer login.')
            return redirect('login')
    else:
        form = RegistroUsuarioForm()
        
    return render(request, 'chamados_ti/registrar.html', {'form': form})

@login_required
def editar_perfil_view(request):
    if request.method == 'POST':
        # Passamos 'instance=request.user' para o Django saber que estamos ATUALIZANDO o usuário logado
        form = EditarPerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Seu perfil foi atualizado com sucesso!')
            return redirect('dashboard')
    else:
        form = EditarPerfilForm(instance=request.user)
        
    return render(request, 'chamados_ti/editar_perfil.html', {'form': form})


# ==================== DASHBOARDS ====================

@login_required
def dashboard(request):
    if request.user.tipo in ['agente_admin', 'agente']:
        return redirect('agente_dashboard')
    # Se não for agente, trata como solicitante
    else: 
        return redirect('solicitante_dashboard')
    
@login_required
def solicitante_dashboard(request):
    if request.user.tipo not in ['solicitante', 'solicitante_admin']:
        return redirect('dashboard')
    
    #Pega a lista base 
    chamados_list = Chamado.objects.filter(solicitante=request.user)

    #Aplica os filtros na lista completa
    status_filtro = request.GET.get('status')
    if status_filtro:
        chamados_list = chamados_list.filter(status=status_filtro)

    data_filtro = request.GET.get('data')
    if data_filtro == 'hoje':
        chamados_list = chamados_list.filter(criado_em__date=datetime.today())
    elif data_filtro == 'semana':
        uma_semana_atras = datetime.today() - timedelta(days=7)
        chamados_list = chamados_list.filter(criado_em__gte=uma_semana_atras)

    ordem = request.GET.get('ordem', '-criado_em')
    chamados_list = chamados_list.order_by(ordem)

    # Paginação (depois dos filtros)
    paginator = Paginator(chamados_list, 12) # chamados por pagina
    page_number = request.GET.get('page')
    chamados_paginados = paginator.get_page(page_number)

    return render(request, 'chamados_ti/solicitante_dashboard.html', {
        'chamados': chamados_paginados, 
        'status_atual': status_filtro,
        'ordem_atual': ordem,
        'data_atual': data_filtro,
    })

@login_required
def agente_dashboard(request):
    if not request.user.is_agente:
        return redirect('dashboard')
    
    # --- LÓGICA DE PERMISSÃO ---
    if request.user.tipo == 'agente_admin':
        # Admin vê TUDO que ja tenha mecanicos atribuidos (removendo o filtro de mecanicos=request.user)
        chamados_list = Chamado.objects.filter(agentes__isnull=False).distinct() # Garante que só traga chamados com mecanicos atribuidos
    else:
        # Mecânico comum vê apenas os dele
        chamados_list = Chamado.objects.filter(agentes=request.user)

    # lógica de filtros continua IGUAL 
    chamados_list = chamados_list.annotate(
        ordem_status=Case(
            When(status='pendente', then=Value(1)),
            When(status='em_progresso', then=Value(2)),
            When(status='concluido', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    )

    status_filtro = request.GET.get('status')
    if status_filtro:
        chamados_list = chamados_list.filter(status=status_filtro)

    data_filtro = request.GET.get('data')
    if data_filtro == 'hoje':
        chamados_list = chamados_list.filter(criado_em__date=datetime.today())
    elif data_filtro == 'semana':
        uma_semana_atras = datetime.today() - timedelta(days=7)
        chamados_list = chamados_list.filter(criado_em__gte=uma_semana_atras)

    # filtro de tipo
    tipo_filtro = request.GET.get('tipo_filtro')
    if tipo_filtro:
        chamados_list = chamados_list.filter(tipo=tipo_filtro)

    # 1. Pega a ordem da URL sem dar um valor padrão (default) ainda
    ordem_selecionada = request.GET.get('ordem')

    base_ordem = ['ordem_status','prioridade', '-criado_em'] # ordem padrão
    if ordem_selecionada:
        # Se o usuário clicou em algum filtro de ordenação (ex: data)
        chamados_list = chamados_list.order_by(*base_ordem, ordem_selecionada, '-criado_em')
    else:
        # Se ele não clicou em nada, usamos a Prioridade como critério seguinte
        chamados_list = chamados_list.order_by(*base_ordem, 'prioridade', '-criado_em')

    # 2. CALCULAR OS TOTAIS ANTES DA PAGINACÃO
    pendentes = chamados_list.filter(status='pendente').count()
    em_progresso = chamados_list.filter(status='em_progresso').count()
    concluidos = chamados_list.filter(status='concluido').count()

    # 3. APLICAR A PAGINACÃO
    itens_por_pagina = 12 
    paginator = Paginator(chamados_list, itens_por_pagina)
    
    page_number = request.GET.get('page')
    chamados_paginados = paginator.get_page(page_number)

    return render(request, 'chamados_ti/agente_dashboard.html', {
        'chamados': chamados_paginados, 
        'pendentes': pendentes,
        'em_progresso': em_progresso,
        'concluidos': concluidos,
        'status_atual': status_filtro,
        'ordem_atual': ordem_selecionada,
        'data_atual': data_filtro, 
        'tipo_atual': tipo_filtro,
    })

@login_required
def dashboard_admin_agente(request):
    if request.user.tipo not in ['agente_admin', 'solicitante_admin']:
        return redirect('dashboard')
    
    # 1 Chamados NOVOS (Aguardando designacao)
    chamados_novos = Chamado.objects.filter(agentes__isnull=True).order_by('-criado_em')
    
    # 2 Chamados EM ANDAMENTO (ja designados)
    queryset_andamento = Chamado.objects.filter(agentes__isnull=False)\
        .select_related('equipamento')\
        .prefetch_related('agentes')\
        .order_by('-criado_em')\
        .distinct()
    
    total_andamento = queryset_andamento.count()
    chamados_em_andamento = queryset_andamento[:10]
    
    # 3 Dados auxiliares para o dashboard
    agentes = Usuario.objects.filter(tipo__in=['agente', 'agente_admin'])
    setores = Setor.objects.all()
    equipamentos = Equipamento.objects.all()
    
    
    return render(request, 'chamados_ti/admin_dashboard.html', {
        'chamados_novos': chamados_novos,
        'chamados_em_andamento': chamados_em_andamento,
        'agentes': agentes,
        'setores': setores,
        'equipamentos': equipamentos,
        'total_andamento': total_andamento
    })

@login_required
def atribuir_chamado(request, chamado_id):
    # 1. Validação do tipo de usuário atualizado
    if request.user.tipo not in ['agente_admin', 'solicitante_admin']:
        return redirect('dashboard')
        
    chamado = get_object_or_404(Chamado, id=chamado_id)
    
    if request.method == 'POST':
        # Captura e salva a nova prioridade
        nova_prioridade = request.POST.get('prioridade')
        if nova_prioridade:
            chamado.prioridade = int(nova_prioridade)
            chamado.save()

        # Atribui a equipe de agentes (atualizado conforme seu novo modelo)
        agentes_ids = request.POST.getlist('agentes')
        if agentes_ids:
            chamado.agentes.set(agentes_ids)
            messages.success(request, f"Chamado {chamado.id} atribuído e prioridade atualizada com sucesso!")
        else:
            # Caso mude apenas a prioridade sem colocar nenhum agente
            messages.warning(request, f"Prioridade do chamado {chamado.id} atualizada, mas nenhuma equipe técnica foi definida.")
            
    return redirect('dashboard_admin_agente')





# ============== SETORES E EQUIPAMENTOS =======================

# ── Endpoint JSON para o JavaScript buscar os equipamentos ──────────────────
def api_equipamentos(request):
    """Retorna todos os equipamentos agrupados por categoria em JSON."""
    grupos = {}
    for cat_valor, cat_label in Equipamento.CATEGORIAS:
        equipamentos = list(
            Equipamento.objects.filter(categoria=cat_valor).values('id', 'nome')
        )
        if equipamentos:
            grupos[cat_label] = equipamentos   # { "Periféricos (...)": [{id, nome}, ...] }
    return JsonResponse(grupos)

@login_required
def gerenciar_setores(request):
    if not request.user.is_agente:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SetorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Setor cadastrado com sucesso!')
            return redirect('gerenciar_setores')
    else:
        form = SetorForm()

    setores = Setor.objects.prefetch_related('equipamentos').order_by('nome')
    return render(request, 'chamados_ti/gerenciar_setores.html', {
        'form': form,
        'setores': setores,
    })


@login_required
def editar_setor(request, pk):
    if not request.user.is_agente:
        return redirect('dashboard')

    setor = get_object_or_404(Setor, pk=pk)

    if request.method == 'POST':
        form = SetorForm(request.POST, instance=setor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Setor atualizado com sucesso!')
            return redirect('gerenciar_setores')
    else:
        form = SetorForm(instance=setor)

    setores = Setor.objects.prefetch_related('equipamentos').order_by('nome')
    return render(request, 'chamados_ti/gerenciar_setores.html', {
        'form': form,
        'setores': setores,
        'editando': True,
        # IDs já vinculados ao setor, para o JS pré-carregar os badges
        'ids_selecionados': list(setor.equipamentos.values_list('id', flat=True)),
    })

@login_required
def gerenciar_equipamentos(request):
    if not request.user.is_agente:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = EquipamentoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Equipamento cadastrado com sucesso!')
            return redirect('gerenciar_equipamentos')
    else:
        form = EquipamentoForm()

    # 1. Correção do nome: 'search' (estava 'serach')
    busca = request.GET.get('search', '')

    # 2. Filtragem dos equipamentos
    equipamentos_list = Equipamento.objects.all().order_by('-id') # Adicionei order_by para os novos aparecerem primeiro
    if busca:
        equipamentos_list = equipamentos_list.filter(
            Q(nome__icontains=busca) | 
            Q(codigo__icontains=busca) |
            Q(energia__numero__icontains=busca)
        )
    
    # 3. Paginação
    paginator = Paginator(equipamentos_list, 10)
    page_number = request.GET.get('page')
    equipamentos = paginator.get_page(page_number)

    # 4. Contador inteligente (mostra o total filtrado)
    total_equipamentos = equipamentos_list.count()
    
    return render(request, 'chamados_ti/gerenciar_equipamentos.html', {
        'form': form,
        'equipamentos': equipamentos,
        'total_equipamentos': total_equipamentos,
        'busca': busca 
    })

@login_required
def editar_equipamento(request, pk):
    if not request.user.is_agente:
        return redirect('dashboard')
    
    equipamento = get_object_or_404(Equipamento, pk=pk)

    if request.method == 'POST':
        form = EquipamentoForm(request.POST, request.FILES, instance=equipamento)
        if form.is_valid():
            form.save()
            return redirect('gerenciar_equipamentos')
    else:
        form = EquipamentoForm(instance=equipamento)

    busca = request.GET.get('search', '')
    
    equipamentos_list = Equipamento.objects.all().order_by('-id')
    if busca:
        equipamentos_list = equipamentos_list.filter(
            Q(nome__icontains=busca)
        )

    paginator = Paginator(equipamentos_list, 10)
    page_number = request.GET.get('page')
    equipamentos_paginados = paginator.get_page(page_number)
    
    return render(request, 'chamados_ti/gerenciar_equipamentos.html', {
        'form': form,
        'equipamentos': equipamentos_paginados,
        'total_equipamentos': equipamentos_list.count(),
        'busca': busca,
        'editando': True # Variável para mudar os textos no HTML
    })



# =================== CHAMADOS ====================

@login_required
def criar_chamado(request):

    if request.method == 'POST':
        form = ChamadoForm(request.POST, request.FILES)

        # Expande o queryset para o Django aceitar o ID do equipamento na validação
        equip_id_post = request.POST.get('equipamento')
        if equip_id_post:
            form.fields['equipamento'].queryset = Equipamento.objects.filter(
                pk=equip_id_post
            )

        if form.is_valid():
            setor_id = request.POST.get('setor_selecionado')
            if not setor_id or setor_id == '':
                messages.error(request, 'Por favor, selecione um setor válido.')
                setores = Setor.objects.order_by('nome')
                return render(request, 'chamados_ti/criar_chamado.html', {
                    'form': form,
                    'setores': setores,
                })
            chamado = form.save(commit=False)
            chamado.solicitante = request.user

            # Salva o setor selecionado no formulário
            if setor_id:
                chamado.setor_id = setor_id

            chamado.save()

            enviar_notificacao_email(chamado, request.get_host())

            for f in request.FILES.getlist('imagens'):
                ImagemChamado.objects.create(chamado=chamado, imagem=f)

            messages.success(request, 'Chamado criado com sucesso!')

            if request.user.tipo == 'agente_admin':
                return redirect('agente_dashboard')
            return redirect('solicitante_dashboard')

        else:
            messages.error(request, 'Erro ao criar chamado. Verifique os campos.')

    else:
        form = ChamadoForm()

    setores = Setor.objects.order_by('nome')

    return render(request, 'chamados_ti/criar_chamado.html', {
        'form': form,
        'setores': setores,
    })

@login_required
def atualizar_status(request, chamado_id):
    if not request.user.is_agente:
        return redirect('dashboard')
    
    if request.user.tipo == 'agente_admin':
        chamado = get_object_or_404(Chamado, id=chamado_id)
    else:
        chamado = get_object_or_404(Chamado, id=chamado_id, agentes=request.user)

    if chamado.status == 'concluido':
        messages.error(request, 'Este chamado já foi concluído.')
        return redirect('dashboard')

    if request.method == 'POST':
        novo_status = request.POST.get('status')
        observacoes = request.POST.get('observacoes', '')
        
        if novo_status in ['pendente', 'em_progresso', 'concluido']:
            chamado.status = novo_status
            
            if novo_status == 'em_progresso' and not chamado.iniciado_em:
                chamado.iniciado_em = timezone.now()
            elif novo_status == 'concluido':
                if not chamado.concluido_em:
                    chamado.concluido_em = timezone.now()
                chamado.concluido_por = request.user
            
            if observacoes:
                chamado.observacoes_agente = observacoes
            
            chamado.save()
            messages.success(request, 'Atualizado com sucesso!')
        
            if novo_status == 'concluido':
                return redirect('detalhe_chamado', chamado_id=chamado.id)
                
            # Se apenas iniciou (em_progresso), mantém na mesma tela para ele ver o cronômetro
            return redirect('atualizar_status', chamado.id)
    
    return render(request, 'chamados_ti/atualizar_status.html', {
        'chamado': chamado
    })

@login_required
@require_POST
def adicionar_mensagem_chamado(request, chamado_id):
    # Pega o chamado ou retorna 404 se não existir
    chamado = get_object_or_404(Chamado, pk=chamado_id)
    
    # Segurança: Impede novas mensagens se o chamado já estiver concluído
    if chamado.status == 'concluido':
        return redirect('detalhe_chamado', chamado_id=chamado.id) 
        
    texto = request.POST.get('texto_mensagem', '').strip()
    
    if texto:
        # 1. Guarda a instância da mensagem criada na variável 'mensagem'
        mensagem = MensagemChamado.objects.create(
            chamado=chamado,
            autor=request.user,
            texto=texto
        )

        # 2. SE O USUÁRIO FOR AGENTE: Processa os arquivos anexados (se houver)
        if getattr(request.user, 'is_agente', False) and request.FILES.getlist('arquivos'):
            for f in request.FILES.getlist('arquivos'):
                ImagemChamado.objects.create(
                    chamado=chamado,
                    mensagem=mensagem,  # <--- Passa a mensagem criada acima
                    imagem=f
                )
        
    # Redireciona o usuário de volta para a rota correspondente
    if not getattr(request.user, 'is_agente', False):
        url_destino = reverse('detalhe_chamado', kwargs={'chamado_id': chamado.id})
    else:
        url_destino = reverse('atualizar_status', kwargs={'chamado_id': chamado.id})

    # Adiciona o fragmento para rolar até o histórico de mensagens
    return redirect(f"{url_destino}#historico-chat")

# api para o JS buscar os equipamentos de um setor específico
@login_required
def api_equipamentos_do_setor(request, setor_id):
    """
    Retorna os equipamentos vinculados a um setor, agrupados por categoria.
    Usado pelo JS do formulário de criar chamado.
    """
    try:
        setor = Setor.objects.prefetch_related('equipamentos').get(pk=setor_id)
    except Setor.DoesNotExist:
        return JsonResponse({}, status=404)

    grupos = {}
    for cat_valor, cat_label in Equipamento.CATEGORIAS:
        equipamentos = list(
            setor.equipamentos.filter(categoria=cat_valor).values('id', 'nome')
        )
        if equipamentos:
            grupos[cat_label] = equipamentos

    return JsonResponse(grupos)



# =================== HISTÓRICO DE CHAMADOS ====================
@login_required
def historicos(request):
    # Mantendo a validação original de permissão
    if not request.user.is_agente:
        return redirect('dashboard')
    
    # Captura dos filtros do GET
    q = request.GET.get('q') or ''
    status_filtro = request.GET.get('status') or ''
    ordenar = request.GET.get('ordenar') or 'recente'

    # Buscamos apenas usuários que já criaram pelo menos um chamado no sistema
    usuarios = Usuario.objects.filter(chamados_criados__isnull=False).distinct()

    # Filtro dinâmico para as anotações numéricas de chamados
    filtro_status = Q()
    if status_filtro:
        filtro_status = Q(chamados_criados__status=status_filtro)

    # Anotações inteligentes: calcula os contadores de cada status para o usuário atual
    usuarios = usuarios.annotate(
        ultima_atividade=Max('chamados_criados__criado_em', filter=filtro_status),
        total_chamados=Count('chamados_criados', filter=filtro_status),
        chamados_pendentes=Count('chamados_criados', filter=Q(chamados_criados__status='pendente')),
        chamados_em_progresso=Count('chamados_criados', filter=Q(chamados_criados__status='em_progresso')),
        concluidos_chamados=Count('chamados_criados', filter=Q(chamados_criados__status='concluido')),
        chamados_abertos=Count('chamados_criados', filter=Q(chamados_criados__status__in=['pendente', 'em_progresso']))
    )

    # Filtro de Busca (Nome, Sobrenome, Usuário ou E-mail)
    if q:
        usuarios = usuarios.filter(
            Q(first_name__icontains=q) | 
            Q(last_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

    # APLICAÇÃO DA ORDENAÇÃO SELECIONADA
    hoje = timezone.now().date()
    if ordenar == 'abertos_primeiro':
        # Ordena pelos que mais possuem chamados em aberto (Fila + Atendimento)
        usuarios = usuarios.order_by('-chamados_abertos', F('ultima_atividade').desc(nulls_last=True))
    
    elif ordenar == 'ultimo_hoje':
        # Ordena colocando quem abriu chamado HOJE primeiro. Os demais vêm depois
        usuarios = usuarios.annotate(
            abriu_hoje=Count('chamados_criados', filter=Q(chamados_criados__criado_em__date=hoje))
        ).order_by('-abriu_hoje', F('ultima_atividade').desc(nulls_last=True))
        
    elif ordenar == 'mais_chamados':
        # Ordena por quem tem maior volume histórico de chamados
        usuarios = usuarios.order_by('-total_chamados', F('ultima_atividade').desc(nulls_last=True))
        
    else: # 'recente'
        # Ordenação padrão: Atividade mais recente primeiro
        usuarios = usuarios.order_by(F('ultima_atividade').desc(nulls_last=True))

    # ================= LOGICA DA PAGINAÇÃO =================
    itens_por_pagina = 10  # quantidade de usuários por página 
    paginator = Paginator(usuarios, itens_por_pagina)
    
    page_number = request.GET.get('page')
    usuarios_paginados = paginator.get_page(page_number)
    # =======================================================


    # PREENCHIMENTO DO PREVIEW (Captura o último objeto Chamado de cada usuário)
    for usuario in usuarios_paginados:
        qs_chamados = Chamado.objects.filter(solicitante=usuario)
        if status_filtro:
            qs_chamados = qs_chamados.filter(status=status_filtro)
        
        # Injeta dinamicamente o último chamado dentro do objeto do usuário
        usuario.ultimo_chamado = qs_chamados.order_by('-criado_em').first()

    # Retorno do Render atualizado com o seu caminho de template original
    return render(request, 'chamados_ti/historicos.html', {
        'usuarios': usuarios_paginados,
        'search_query': q,
        'ordenacao_selecionada': ordenar,
    })

def historico_usuario(request, usuario_id):
    if not request.user.is_agente and request.user.id != usuario_id:
        return redirect('dashboard')
    
    # 1. Lista base dos chamados DO solicitante 
    chamados_list = Chamado.objects.filter(solicitante_id=usuario_id)

    # 2. Aplica os filtros de status e ordenação
    status_filtro = request.GET.get('status') or ''
    tipo_filtro = request.GET.get('tipo') or ''
    ordenar_por = request.GET.get('ordenar') or 'recentes'

    # 3. Se tiver filtro de status, aplica
    if status_filtro:
        chamados_list = chamados_list.filter(status=status_filtro)
    if tipo_filtro:
        chamados_list = chamados_list.filter(tipo=tipo_filtro)

    # 4. Ordenação
    chamados_list = chamados_list.annotate(
        ordem_status=Case(
            When(status='pendente', then=Value(1)),
            When(status='em_progresso', then=Value(2)),
            When(status='concluido', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    )
    
    # 5. Ordenação dinamica ↓
    
    # Se o usuário escolheu "antigos", ordena do mais antigo para o mais recente
    if ordenar_por == 'antigos':
        base_ordem = ['criado_em']
    
    # Se o usuário escolheu "recentes", ordena do mais recente para o mais antigo
    elif ordenar_por == 'recentes':
        base_ordem = ['-criado_em']
    
    # Ordenação padrão: pendentes primeiro, depois em progresso, depois concluídos
    else:
        base_ordem = ['ordem_status', '-criado_em']

    # Aplica a ordenação final, incluindo prioridade como critério secundário
    chamados_list = chamados_list.order_by(*base_ordem, 'prioridade', '-criado_em')

    # 6. Paginacao
    itens_por_pagina = 12
    paginator = Paginator(chamados_list, itens_por_pagina)

    page_number = request.GET.get('page')
    chamados_paginados = paginator.get_page(page_number)

    return render(request, 'chamados_ti/historico_usuario.html', {
        'chamados': chamados_paginados,
        'usuario_id': usuario_id,
        'status_selecionado': status_filtro,  # passar todos os filtros pro template
        'tipo_selecionado': tipo_filtro,
        'ordenacao_selecionada': ordenar_por,
    })

def detalhe_chamado(request, chamado_id):
    
    # Captura o chamado ou retorna 404 de forma limpa, otimizando as tabelas vinculadas
    chamado = get_object_or_404(
        Chamado.objects.select_related('solicitante', 'equipamento'), id=chamado_id
        )
    
    return render(request, 'chamados_ti/detalhe_chamado.html',{
        'chamado':chamado
    })