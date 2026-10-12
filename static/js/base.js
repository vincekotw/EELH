/**
 * Comportamiento global del topbar y menú móvil.
 *
 * El menú, al abrirse en móvil, se MUEVE al <body> para escapar
 * del contexto de apilamiento del header. Esto garantiza que
 * quede por encima de cualquier iframe (mapa, embeds, etc.)
 * incluso en iOS Safari.
 */
(function () {
    'use strict';

    var toggle = document.getElementById('nav-toggle');
    var menu = document.getElementById('nav-menu');
    var topbar = document.querySelector('.topbar');
    if (!toggle || !menu || !topbar) return;

    // Guardamos el padre original para devolver el menú al cerrar
    var padreOriginal = menu.parentNode;

    function esMovil() {
        return window.innerWidth <= 900;
    }

    function abrirMenu() {
        // En móvil, mover el menú al <body> para que quede por
        // encima de cualquier iframe, sin importar z-index.
        if (esMovil() && menu.parentNode !== document.body) {
            document.body.appendChild(menu);
            menu.style.position = 'fixed';
            menu.style.top = topbar.offsetHeight + 'px';
            menu.style.left = '0';
            menu.style.right = '0';
            menu.style.zIndex = '999999';
            menu.style.display = 'flex';
        }
        toggle.classList.add('active');
        menu.classList.add('open');
    }

    function cerrarMenu() {
        toggle.classList.remove('active');
        menu.classList.remove('open');

        // Limpiar estilos inline
        menu.style.position = '';
        menu.style.top = '';
        menu.style.left = '';
        menu.style.right = '';
        menu.style.zIndex = '';
        menu.style.display = '';

        // Devolverlo a su padre original si lo movimos
        if (menu.parentNode !== padreOriginal) {
            padreOriginal.appendChild(menu);
        }
    }

    window.cerrarMenuNav = cerrarMenu;

    toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        if (menu.classList.contains('open')) {
            cerrarMenu();
        } else {
            abrirMenu();
        }
    });

    menu.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', cerrarMenu);
    });

    document.addEventListener('click', function (e) {
        if (!menu.contains(e.target) && !toggle.contains(e.target)) {
            cerrarMenu();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') cerrarMenu();
    });

    // Cierre defensivo en todos los eventos posibles
    document.addEventListener('DOMContentLoaded', cerrarMenu);
    if (document.readyState !== 'loading') cerrarMenu();

    window.addEventListener('pageshow', cerrarMenu);
    window.addEventListener('pagehide', cerrarMenu);
    window.addEventListener('beforeunload', cerrarMenu);

    window.addEventListener('orientationchange', function () {
        setTimeout(cerrarMenu, 100);
    });

    window.addEventListener('resize', function () {
        if (!esMovil()) cerrarMenu();
    });

    // Martillo: cerrar varias veces por si el DOM se restaura tarde
    setTimeout(cerrarMenu, 0);
    setTimeout(cerrarMenu, 100);
    setTimeout(cerrarMenu, 400);
})();