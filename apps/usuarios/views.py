from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetView,
)
from django.shortcuts import redirect, render
from .models import Profile
from .forms import RegistroForm, CustomAuthenticationForm


# ═══════════════════════════════════════════════════════════════
# REGISTRO
# ═══════════════════════════════════════════════════════════════
def registro(request):
    if request.user.is_authenticated:
        return redirect('usuarios:perfil')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f'¡Bienvenido, {user.username}! Tu cuenta fue creada.',
            )
            return redirect('usuarios:perfil')
    else:
        form = RegistroForm()

    return render(request, 'usuarios/registro.html', {'form': form})


# ═══════════════════════════════════════════════════════════════
# LOGIN / LOGOUT (subclases para mensajes)
# ═══════════════════════════════════════════════════════════════



class CustomLoginView(LoginView):
    template_name = 'usuarios/login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Bienvenido de vuelta, {form.get_user().username}',
        )
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    next_page = 'home'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, 'Sesión cerrada correctamente.')
        return super().dispatch(request, *args, **kwargs)


# ═══════════════════════════════════════════════════════════════
# PERFIL
# ═══════════════════════════════════════════════════════════════
@login_required
def perfil(request):
    # Fallback defensivo: crear el Profile si no existe
    profile, _ = Profile.objects.get_or_create(user=request.user)

    circuitos_vinculados = (
        request.user.circuitos_vinculados
        .select_related('circuito')
        .order_by('circuito__codigo')
    )
    notif_no_leidas = (
        request.user.notificaciones
        .filter(leida=False)
        .count()
    )

    return render(request, 'usuarios/perfil.html', {
        'profile': profile,
        'circuitos_vinculados': circuitos_vinculados,
        'notif_no_leidas': notif_no_leidas,
    })

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q

from apps.circuitos.models import Circuito
from .models import CircuitoUsuario


# ═══════════════════════════════════════════════════════════════
# LISTA DE CIRCUITOS (para vincular)
# ═══════════════════════════════════════════════════════════════
@login_required
def circuitos_disponibles(request):
    """
    Página con todos los circuitos. Muestra un check para
    indicar cuáles ya están vinculados al usuario.
    """
    # IDs de circuitos ya vinculados por este usuario
    vinculados_ids = set(
        CircuitoUsuario.objects
        .filter(user=request.user)
        .values_list('circuito_id', flat=True)
    )

    # Búsqueda
    q = (request.GET.get('q') or '').strip()
    circuitos = Circuito.objects.all().order_by('codigo')

    if q:
        circuitos = circuitos.filter(
            Q(codigo__icontains=q)
            | Q(direccion__icontains=q)
            | Q(municipio__icontains=q)
        )

    # Anotar cada circuito con si está vinculado
    for c in circuitos:
        c.esta_vinculado = c.id in vinculados_ids

    return render(request, 'usuarios/circuitos_disponibles.html', {
        'circuitos': circuitos,
        'vinculados_ids': vinculados_ids,
        'q': q,
        'total_vinculados': len(vinculados_ids),
    })


# ═══════════════════════════════════════════════════════════════
# VINCULAR
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def vincular_circuito(request):
    codigo = (request.POST.get('codigo') or '').strip().upper()

    circuito = Circuito.objects.filter(codigo__iexact=codigo).first()
    if not circuito:
        return JsonResponse({'error': f'Circuito {codigo} no existe'}, status=404)

    _, created = CircuitoUsuario.objects.get_or_create(
        user=request.user,
        circuito=circuito,
    )

    total = CircuitoUsuario.objects.filter(user=request.user).count()

    return JsonResponse({
        'ok': True,
        'codigo': circuito.codigo,
        'created': created,
        'total_vinculados': total,
    })


# ═══════════════════════════════════════════════════════════════
# DESVINCULAR
# ═══════════════════════════════════════════════════════════════
@login_required
@require_POST
def desvincular_circuito(request):
    codigo = (request.POST.get('codigo') or '').strip().upper()

    circuito = Circuito.objects.filter(codigo__iexact=codigo).first()
    if not circuito:
        return JsonResponse({'error': f'Circuito {codigo} no existe'}, status=404)

    borrados, _ = CircuitoUsuario.objects.filter(
        user=request.user,
        circuito=circuito,
    ).delete()

    total = CircuitoUsuario.objects.filter(user=request.user).count()

    return JsonResponse({
        'ok': True,
        'codigo': circuito.codigo,
        'deleted': borrados,
        'total_vinculados': total,
    })