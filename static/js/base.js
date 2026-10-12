/**
 * Comportamiento global del topbar y menú móvil.
 *
 * Estrategia defensiva: el menú NUNCA debe quedar abierto al
 * cargar una página nueva, venga de donde venga (recarga,
 * navegación normal, bfcache, restauración asíncrona del DOM).
 * Por eso cerramos el menú desde múltiples eventos, sin confiar
 * en que un único evento sea suficiente.
 */
(function () {
    'use strict';

    var toggle = document.getElementById('nav-toggle');
    var menu = document.getElementById('nav-menu');
    if (!toggle || !menu) return;

    // ── Estado ─────────────────────────────────────────────
    function cerrarMenu() {
        toggle.classList.remove('active');
        menu.classList.remove('open');
    }

    function abrirMenu() {
        toggle.classList.add('active');
        menu.classList.add('open');
    }

    // Exponer al scope global por si otra página lo necesita
    window.cerrarMenuNav = cerrarMenu;

    // ── Interacciones básicas ──────────────────────────────
    toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        if (menu.classList.contains('open')) {
            cerrarMenu();
        } else {
            abrirMenu();
        }
    });

    // Cerrar al hacer clic en cualquier enlace del menú
    menu.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', cerrarMenu);
    });

    // Cerrar al hacer clic fuera del menú
    document.addEventListener('click', function (e) {
        if (!menu.contains(e.target) && !toggle.contains(e.target)) {
            cerrarMenu();
        }
    });

    // Cerrar con la tecla Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && menu.classList.contains('open')) {
            cerrarMenu();
        }
    });

    // ── Cierre defensivo en todos los eventos posibles ─────

    // 1) Al construir el DOM
    document.addEventListener('DOMContentLoaded', cerrarMenu);

    // 2) Si el DOM ya está listo (script cargado al final del body)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', cerrarMenu);
    } else {
        cerrarMenu();
    }

    // 3) Al volver desde bfcache.
    //    No comprobamos e.persisted porque algunos navegadores
    //    no lo marcan bien. Cerrar siempre es correcto: si ya
    //    estaba cerrado, cerrarMenu() no hace nada.
    window.addEventListener('pageshow', cerrarMenu);

    // 4) Antes de salir de la página, cerramos por si el
    //    navegador guarda el estado actual en bfcache.
    window.addEventListener('pagehide', cerrarMenu);
    window.addEventListener('beforeunload', cerrarMenu);

    // 5) Al cambiar la orientación del dispositivo.
    //    Pequeño delay porque algunos navegadores disparan el
    //    evento antes de aplicar el nuevo layout.
    window.addEventListener('orientationchange', function () {
        setTimeout(cerrarMenu, 100);
    });

    // 6) Al pasar de móvil a desktop, cerrar el menú para que
    //    no quede residual al cambiar el tamaño.
    window.addEventListener('resize', function () {
        if (window.innerWidth > 900) {
            cerrarMenu();
        }
    });

    // 7) Martillo: cerrar varias veces tras la carga para
    //    cubrir cualquier restauración tardía del DOM por
    //    parte del navegador.
    setTimeout(cerrarMenu, 0);
    setTimeout(cerrarMenu, 50);
    setTimeout(cerrarMenu, 200);
    setTimeout(cerrarMenu, 500);
})();