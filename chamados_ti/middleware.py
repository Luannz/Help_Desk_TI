# chamados_ti/middleware.py

from django.shortcuts import redirect
from django.urls import reverse

class ForcarTrocaSenhaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Se o usuário precisa trocar a senha
            if getattr(request.user, 'forcar_troca_senha', False):
                # Rotas liberadas que ele PODE acessar (Troca de senha, Logout e arquivos estáticos)
                rotas_liberadas = [
                    reverse('primeiro_acesso_senha'),
                    reverse('logout'),
                ]

                # Se a página atual NÃO for uma das liberadas, força o redirecionamento
                if request.path not in rotas_liberadas and not request.path.startswith('/static/'):
                    return redirect('primeiro_acesso_senha')

        response = self.get_response(request)
        return response