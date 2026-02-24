from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Count
from obras.models import Obra, LocalObra
from suprimentos.models import ItemMapa, Insumo


def is_staff_or_superuser(user):
    """Verifica se o usuário é staff ou superusuário."""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
def admin_central(request):
    """Página central de administração."""
    # Estatísticas
    stats = {
        'total_usuarios': User.objects.count(),
        'total_obras': Obra.objects.count(),
        'total_insumos': Insumo.objects.count(),
        'total_itens_mapa': ItemMapa.objects.count(),
        'usuarios_por_grupo': Group.objects.annotate(count=Count('user')).values('name', 'count'),
    }
    
    # Últimos usuários
    ultimos_usuarios = User.objects.order_by('-date_joined')[:10]
    
    # Obras ativas
    obras_ativas = Obra.objects.filter(ativa=True).order_by('nome')
    
    context = {
        'stats': stats,
        'ultimos_usuarios': ultimos_usuarios,
        'obras_ativas': obras_ativas,
    }
    
    return render(request, 'accounts/admin_central.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def criar_usuario(request):
    """Cria um novo usuário e atribui grupo."""
    grupos = Group.objects.all().order_by('name')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        grupo_id = request.POST.get('grupo')
        is_staff = request.POST.get('is_staff') == 'on'
        
        if not username or not password:
            messages.error(request, 'Usuário e senha são obrigatórios.')
            return render(request, 'accounts/criar_usuario.html', {'grupos': grupos})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Este usuário já existe.')
            return render(request, 'accounts/criar_usuario.html', {'grupos': grupos})
        
        # Criar usuário
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=is_staff
        )
        
        # Atribuir grupo
        if grupo_id:
            grupo = get_object_or_404(Group, id=grupo_id)
            user.groups.add(grupo)
            messages.success(request, f'Usuário "{username}" criado e adicionado ao grupo "{grupo.name}"!')
        else:
            messages.success(request, f'Usuário "{username}" criado! (sem grupo)')
        
        return redirect('admin_central')
    
    return render(request, 'accounts/criar_usuario.html', {'grupos': grupos})


@login_required
@user_passes_test(is_staff_or_superuser)
def gerenciar_usuarios(request):
    """Lista e gerencia usuários."""
    usuarios = User.objects.all().order_by('-date_joined')
    grupos = Group.objects.all().order_by('name')
    
    # Filtro por grupo
    grupo_filtro = request.GET.get('grupo')
    if grupo_filtro:
        usuarios = usuarios.filter(groups__id=grupo_filtro)
    
    # Busca
    search = request.GET.get('search', '')
    if search:
        usuarios = usuarios.filter(
            username__icontains=search
        ) | usuarios.filter(
            first_name__icontains=search
        ) | usuarios.filter(
            last_name__icontains=search
        ) | usuarios.filter(
            email__icontains=search
        )
    
    context = {
        'usuarios': usuarios,
        'grupos': grupos,
        'grupo_filtro': grupo_filtro,
        'search': search,
    }
    
    return render(request, 'accounts/gerenciar_usuarios.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def editar_usuario(request, user_id):
    """Edita usuário e grupos."""
    user = get_object_or_404(User, id=user_id)
    grupos = Group.objects.all().order_by('name')
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.is_staff = request.POST.get('is_staff') == 'on'
        user.is_active = request.POST.get('is_active') == 'on'
        
        # Atualizar senha se fornecida
        nova_senha = request.POST.get('password')
        if nova_senha:
            user.set_password(nova_senha)
        
        user.save()
        
        # Atualizar grupos
        grupos_selecionados = request.POST.getlist('grupos')
        user.groups.clear()
        for grupo_id in grupos_selecionados:
            grupo = get_object_or_404(Group, id=grupo_id)
            user.groups.add(grupo)
        
        messages.success(request, f'Usuário "{user.username}" atualizado!')
        return redirect('gerenciar_usuarios')
    
    grupos_usuario = user.groups.all()
    
    context = {
        'user': user,
        'grupos': grupos,
        'grupos_usuario': grupos_usuario,
    }
    
    return render(request, 'accounts/editar_usuario.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def criar_obra(request):
    """Cria uma nova obra."""
    if request.method == 'POST':
        codigo_sienge = request.POST.get('codigo_sienge')
        nome = request.POST.get('nome')
        ativa = request.POST.get('ativa') == 'on'
        
        if not codigo_sienge or not nome:
            messages.error(request, 'Código e nome são obrigatórios.')
            return render(request, 'accounts/criar_obra.html')
        
        if Obra.objects.filter(codigo_sienge=codigo_sienge).exists():
            messages.error(request, 'Já existe uma obra com este código.')
            return render(request, 'accounts/criar_obra.html')
        
        obra = Obra.objects.create(
            codigo_sienge=codigo_sienge,
            nome=nome,
            ativa=ativa
        )
        
        messages.success(request, f'Obra "{obra.nome}" criada!')
        return redirect('admin_central')
    
    return render(request, 'accounts/criar_obra.html')


@login_required
@user_passes_test(is_staff_or_superuser)
def gerenciar_obras(request):
    """Lista e gerencia obras."""
    obras = Obra.objects.all().order_by('nome')
    
    # Filtro
    ativa_filtro = request.GET.get('ativa')
    if ativa_filtro == '1':
        obras = obras.filter(ativa=True)
    elif ativa_filtro == '0':
        obras = obras.filter(ativa=False)
    
    context = {
        'obras': obras,
        'ativa_filtro': ativa_filtro,
    }
    
    return render(request, 'accounts/gerenciar_obras.html', context)

