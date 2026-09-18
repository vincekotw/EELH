"""
Genera claves VAPID para Web Push.
Compatible con py-vapid 1.9+ y 2.x.
"""

import base64
import sys


def generar():
    try:
        from py_vapid import Vapid
    except ImportError:
        print('❌ py-vapid no está instalado. Ejecuta: pip install py-vapid')
        return

    # ── Método 1: Vapid().generate_keys() → dict ─────────────
    try:
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, PrivateFormat, NoEncryption,
        )

        vapid = Vapid()
        vapid.generate_keys()

        # Clave privada (PEM)
        private_bytes = vapid.private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )
        private_pem = private_bytes.decode('utf-8')

        # Clave pública (raw uncompressed point → base64url)
        public_bytes = vapid.public_key.public_bytes(
            encoding=Encoding.X962,
            format=PublicFormat.UncompressedPoint,
        )
        public_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b'=').decode('utf-8')

        # Clave privada en base64url (para pywebpush)
        private_raw = vapid.private_key.private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )
        private_b64 = base64.urlsafe_b64encode(private_raw).rstrip(b'=').decode('utf-8')

        print('═' * 70)
        print('  VAPID KEYS GENERADAS')
        print('═' * 70)
        print()
        print(f'VAPID_PUBLIC_KEY={public_b64}')
        print()
        print(f'VAPID_PRIVATE_KEY={private_pem}')
        print()
        print('═' * 70)
        print('  Copia estos valores a Render → Environment Variables')
        print('═' * 70)
        print()
        print('Notas:')
        print('  - VAPID_PUBLIC_KEY: cadena base64url corta (el navegador la usa)')
        print('  - VAPID_PRIVATE_KEY: bloque PEM (el servidor firma con ella)')
        print('  - Guarda ambos valores en un lugar seguro')
        print()

    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()


generar()