"""
Importa el backup usando bulk_create en lugar de loaddata.
Maneja:
  - Campos M2M (many-to-many) → .set()
  - Campos FK con natural keys (ej: ["vince"]) → resuelve a pk
  - PK con natural keys → resuelve a pk
"""

import json
import os
import sys
import time

from django.apps import apps
from django.db import transaction


ARCHIVO = 'backup.json'
BLOQUE = 500


ORDEN_MODELOS = [
    # Ya importados — comentados
    # 'auth.user',
    # 'auth.group',
    # 'auth.permission',
    # 'telegram_base.estadoscraper',
    # 'telegram_base.mensaje',
    # 'telegram_base.scraperun',
    # 'circuitos.circuito',
    # 'circuitos.eventocircuito',
    # 'circuitos.alertamasiva',
    # 'circuitos.snapshotaverias',
    # 'circuitos.circuitodaf',

    # Pendientes
    'usuarios.profile',
    'usuarios.circuitousuario',
    'usuarios.notificacion',
    'usuarios.navegacionlog',
]


def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()


def get_model(model_label):
    try:
        return apps.get_model(model_label)
    except LookupError:
        return None


def _resolver_a_pk(model_class, field_name, valor):
    """
    Convierte un valor FK (numérico o natural key) a un pk numérico.
    """
    if not isinstance(valor, list):
        return valor

    try:
        field = model_class._meta.get_field(field_name)
        related_model = field.related_model
        obj = related_model._default_manager.get_by_natural_key(*valor)
        return obj.pk
    except Exception as e:
        log(f'    ⚠️ No se pudo resolver {field_name}={valor}: {e}')
        return None


def clasificar_campos(model_class, fields_dict, pk_value=None):
    """Separa campos normales, M2M y resuelve natural keys."""
    m2m_names = {f.name for f in model_class._meta.many_to_many}

    fk_names = set()
    for f in model_class._meta.get_fields():
        if f.is_relation and not f.many_to_many and not f.auto_created:
            if hasattr(f, 'attname') and f.attname != f.name:
                fk_names.add(f.name)

    normales = {}
    m2m = {}

    for key, value in fields_dict.items():
        if key in m2m_names:
            m2m[key] = value
        elif key in fk_names:
            valor_pk = _resolver_a_pk(model_class, key, value)
            normales[f'{key}_id'] = valor_pk
        else:
            normales[key] = value

    if isinstance(pk_value, list):
        try:
            obj = model_class._default_manager.get_by_natural_key(*pk_value)
            pk_value = obj.pk
        except Exception:
            pk_value = None

    return normales, m2m, pk_value


def importar():
    if not os.path.exists(ARCHIVO):
        log(f'❌ No existe {ARCHIVO}')
        return

    log(f'Leyendo {ARCHIVO}...')
    with open(ARCHIVO, encoding='utf-8') as f:
        data = json.load(f)

    log(f'Total objetos: {len(data)}')

    por_modelo = {}
    for obj in data:
        por_modelo.setdefault(obj['model'], []).append(obj)

    log(f'Modelos: {len(por_modelo)}')
    log('')

    total = 0
    errores = []

    for modelo in ORDEN_MODELOS:
        if modelo not in por_modelo:
            continue

        objetos_data = por_modelo[modelo]
        model_class = get_model(modelo)
        if not model_class:
            log(f'⚠️  Modelo desconocido: {modelo}')
            continue

        log(f'═══ {modelo}: {len(objetos_data)} objetos ═══')

        for i in range(0, len(objetos_data), BLOQUE):
            chunk_data = objetos_data[i:i + BLOQUE]
            num = i // BLOQUE + 1
            total_bloques = (len(objetos_data) + BLOQUE - 1) // BLOQUE

            instancias = []
            m2m_por_pk = {}

            for d in chunk_data:
                campos_normales, campos_m2m, pk_resuelto = clasificar_campos(
                    model_class, d['fields'], d.get('pk'),
                )

                try:
                    obj = model_class(**campos_normales)
                except Exception as e:
                    log(f'    ❌ Error construyendo {modelo} pk={d.get("pk")}: {e}')
                    log(f'       campos: {list(campos_normales.keys())}')
                    raise

                if pk_resuelto is not None:
                    obj.pk = pk_resuelto
                instancias.append(obj)

                if campos_m2m:
                    m2m_por_pk[obj.pk] = campos_m2m

            log(f'  Bloque {num}/{total_bloques} ({len(instancias)} obj)...')
            sys.stdout.flush()

            try:
                t0 = time.time()

                with transaction.atomic():
                    model_class.objects.bulk_create(
                        instancias,
                        batch_size=BLOQUE,
                        ignore_conflicts=True,
                    )

                    for pk, campos_m2m in m2m_por_pk.items():
                        try:
                            obj = model_class.objects.get(pk=pk)
                        except model_class.DoesNotExist:
                            continue

                        for campo, valores in campos_m2m.items():
                            try:
                                getattr(obj, campo).set(valores)
                            except Exception as e:
                                log(f'    ⚠️ M2M {campo} pk={pk}: {e}')

                elapsed = time.time() - t0
                log(f'    ✅ {elapsed:.2f}s')
                total += len(instancias)

            except Exception as e:
                msg = f'{modelo} bloque {num}: {e}'
                log(f'    ❌ {msg}')
                errores.append(msg)
                if num == 1:
                    log(f'    ⛔ Deteniendo importación de {modelo}')
                    break

        log('')

    log('═' * 55)
    log(f'  Importados: {total}')
    log(f'  Errores:    {len(errores)}')
    if errores:
        for e in errores[:10]:
            log(f'  - {e}')


importar()