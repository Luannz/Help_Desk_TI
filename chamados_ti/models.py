# ==================== MODELS.PY ====================
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from PIL import Image, ImageOps
import os
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files import File
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import time

class Usuario(AbstractUser):
    TIPO_CHOICES = [
        ('solicitante', 'Solicitante'),
        ('agente', 'Agente'),
        ('agente_admin', 'Agente Admin'),
        ('solicitante_admin', 'Solicitante Admin'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    setor = models.ForeignKey('Setor', on_delete=models.SET_NULL, null=True, blank=True)
    telefone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(unique=True)
    
    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
    @property
    def is_agente(self):
        """Retorna True se o usuário for qualquer tipo de agente, caso contrário, retorna False."""
        return self.tipo in ['agente', 'agente_admin']


class Equipamento(models.Model):
    CATEGORIAS = [
        ('perifericos', 'Periféricos'),
        ('hardware', 'Hardware / Computadores'),
        ('rede', 'Rede & Conectividade'),
        ('suprimentos', 'Suprimentos & Impressão'),
    ]
    
    nome = models.CharField(max_length=100)
    categoria = models.CharField(max_length=30, choices=CATEGORIAS, default='perifericos')

    def __str__(self):
        return self.nome
        
    class Meta:
        ordering = ['categoria', 'nome']  # Garante a proximidade por categoria por padrão

class Setor(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    # Relação Muitos-para-Muitos abrangente
    equipamentos = models.ManyToManyField(Equipamento, blank=True, related_name='setores')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Setor'
        verbose_name_plural = 'Setores'
        ordering = ['nome']
    
    def __str__(self):
        return self.nome

def validar_tamanho_imagem(value):
    limit = 5 * 1024 * 1024  # 5MB
    if value.size > limit:
        raise ValidationError('A imagem é muito pesada. O limite é de 5MB.')
    
def caminho_imagem_equipamento(instance, filename):
    # Pega a extensao original e força para minúsculo (.PNG > .png)
    extensao = os.path.splitext(filename)[1].lower()
    
    # Se por algum motivo o código estiver vazio, usa o nome ou um padrão
    # pra evita erros se o campo codigo falhar por algum motivo
    prefixo = instance.codigo if instance.codigo else "equip"
    
    # Gera o tempo no caso chamado timestamp (Ex: 1705934123)
    timestamp = int(time.time())
    
    # Nome final: codigo_equipamento_1705934123.png
    novo_nome = f"{prefixo}_{timestamp}{extensao}"
    
    # Retorna o caminho final dentro da pasta media
    return os.path.join('equipamentos/', novo_nome)


class Chamado(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('em_progresso', 'Em Progresso'),
        ('concluido', 'Concluído'),
    ]
    
    TIPO_CHOICES = [
        ('equipamento', 'Equipamento'),
        ('sistema', 'Sistema'),
        ('duvidas', 'Dúvidas'),
    ]
    
    PRIORIDADE_CHOICES = [
        (1, 'Alta'),
        (2, 'Média'),
        (3, 'Baixa'),
    ]
    
    solicitante = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='chamados_criados')
    agentes = models.ManyToManyField(Usuario, related_name='chamados_atribuidos', blank=True)  

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    setor = models.ForeignKey('Setor', on_delete=models.PROTECT,related_name='chamados')
    equipamento = models.ForeignKey(Equipamento, on_delete=models.SET_NULL, null=True, blank=True)
    subcategoria_duvida = models.CharField(max_length=100, null=True, blank=True, help_text="Ex: Excel, e-mail, rede, se tipo for 'duvida'")

    descricao = models.TextField()

    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    prioridade = models.IntegerField(default=3, choices=PRIORIDADE_CHOICES)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    concluido_por = models.ForeignKey(Usuario,on_delete=models.SET_NULL, null=True, blank=True, related_name='chamados_concluidos')

    observacoes_agente = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Chamado'
        verbose_name_plural = 'Chamados'
        ordering = ['-criado_em']

    @property
    def nome_setor(self):
        if self.setor:
            return self.setor.nome
        return "N/A"

    def esta_concluido(self):
        return self.status == 'concluido'

    def pode_mudar_status(self, novo_status):
        if self.status == 'concluido':
            return False
        return True

    def __str__(self):
        return f"#{self.id} - {self.get_status_display()}"
    
    def tempo_aberto(self):
        """
        Retorna o tempo que o chamado ficou/está aberto
        """
        fim = self.concluido_em or timezone.now()
        return fim - self.criado_em

    def tempo_aberto_formatado(self):
        fim = self.concluido_em or timezone.now()
        delta = fim - self.criado_em

        total_minutos = int(delta.total_seconds() // 60)
        horas = total_minutos // 60
        minutos = total_minutos % 60
        dias = horas // 24
        horas_restantes = horas % 24

        if dias > 0:
            return f"{dias}d {horas_restantes}h"
        elif horas > 0:
            return f"{horas}h {minutos}min"
        else:
            return f"{minutos}min"
    
    def tempo_execucao_formatado(self):
        """
        Retorna apenas o tempo em que o mecânico esteve trabalhando no chamado
        (de 'em_progresso' até 'concluido')
        """
        if not self.iniciado_em:
            return "Não iniciado"
        
        # Se concluido, usa a data de conclusao, Se ainda em progresso, usa o agora
        fim = self.concluido_em or timezone.now()
        delta = fim - self.iniciado_em

        total_segundos = int(delta.total_seconds())
        if total_segundos < 0: total_segundos = 0 
        
        horas, resto = divmod(total_segundos, 3600)
        minutos, segundos = divmod(resto, 60)
        dias, horas = divmod(horas, 24)

        if dias > 0:
            return f"{dias}d {horas}h"
        elif horas > 0:
            return f"{horas}h {minutos}min"
        elif minutos > 0:
            return f"{minutos}min"
        else:
            return f"{segundos}seg"

    def save(self, *args, **kwargs):
    # salva o chamado primeiro
        super().save(*args, **kwargs)

        # Se concluido processa as fotos para economizar espaço
        if self.status == 'concluido':
            imagens = self.imagens.all()
            
            for img_obj in imagens:
                if img_obj.imagem:
                    # 1 Abrir a imagem original
                    img_path = img_obj.imagem.path
                    
                    # Verifica se o arquivo existe e se ja nao é um .webp (para não processar duas vezes)
                    if os.path.exists(img_path) and not img_path.lower().endswith('.webp'):
                        img = Image.open(img_path)

                        #Girar a foto que vem girada do celular
                        img = ImageOps.exif_transpose(img)

                        #aqui ele garante que a imagem seja no modo RGB
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        # 2 Redimensionar (Mantendo a proporção)
                        # Se a foto for gigante, limita a largura máxima para 800px
                        max_size = (800, 800)
                        img.thumbnail(max_size, Image.LANCZOS)

                        # 3 Converter para WebP em memória
                        temp_thumb = BytesIO()
                        img.save(temp_thumb, format='WEBP', quality=70) # Qualidade 70 
                        temp_thumb.seek(0)

                        # 4 Atualiza o arquivo no objeto
                        # Muda a extensão do nome do arquivo
                        nome_arquivo = os.path.splitext(os.path.basename(img_path))[0] + ".webp"
                        
                        # Salva o novo arquivo e deleta o antigo automaticamente
                        img_obj.imagem.save(nome_arquivo, ContentFile(temp_thumb.read()), save=False)
                        img_obj.save()
                        
                        # 5 Remove o arquivo original antigo  
                        # mas para garantir espaço em disco imediato):
                        if os.path.exists(img_path) and not img_path.endswith('.webp'):
                            os.remove(img_path)

class ImagemChamado(models.Model):
    chamado = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField(upload_to='chamados/')
    descricao = models.CharField(max_length=200, blank=True)
    enviado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Imagem do Chamado'
        verbose_name_plural = 'Imagens dos Chamados'
        ordering = ['enviado_em']
    
    def __str__(self):
        return f"Imagem #{self.id} - Chamado #{self.chamado.id}"
    

class MensagemChamado(models.Model):
    # vincular a mensagem a um chamado específico
    chamado = models.ForeignKey('Chamado', on_delete=models.CASCADE, related_name='mensagens')
    
    # vincular a mensagem a um usuário específico (quem enviou)
    autor = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    
    # texto da mensagem
    texto = models.TextField()

    # registro da data e hora em que a mensagem foi enviada, no caso aqui pega automatico por causa do autonow_add
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']  # Ordena por data de criação, do mais antigo para o mais recente
    def __str__(self):
        return f"Mensagem de {self.autor.username} no Chamado #{self.chamado.id}"