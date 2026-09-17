"""
Crea Profile para usuarios que no lo tengan.
Necesario para usuarios creados ANTES de implementar el signal.
"""
from django.contrib.auth.models import User
from apps.usuarios.models import Profile


print('═' * 55)
print('  CREANDO PROFILES FALTANTES')
print('═' * 55)

usuarios_sin_profile = []
for user in User.objects.all():
    profile, created = Profile.objects.get_or_create(user=user)
    if created:
        usuarios_sin_profile.append(user.username)

print(f'Usuarios totales: {User.objects.count()}')
print(f'Profiles creados: {len(usuarios_sin_profile)}')

if usuarios_sin_profile:
    print()
    print('Usuarios procesados:')
    for u in usuarios_sin_profile:
        print(f'  ✓ {u}')
else:
    print()
    print('Todos los usuarios ya tenían Profile.')

print()
print('Verificación final:')
print(f'  Users:    {User.objects.count()}')
print(f'  Profiles: {Profile.objects.count()}')