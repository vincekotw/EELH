/**
 * Tabla de circuitos con filtros, ordenamiento y paginación.
 * Todo el filtrado es client-side: los datos vienen embebidos
 * desde Django en window.CIRCUITOS_DATA.
 */

(function () {
    'use strict';

    // ─── Estado ─────────────────────────────────────────────
    const state = {
        filtros: {
            busqueda: '',
            estado: '',
            municipio: '',
            ciclo: '',
            minAfectaciones: 0,
        },
        orden: { campo: 'codigo', dir: 'asc' },
        page: 1,
        pageSize: 50,
    };

    const datos = window.CIRCUITOS_DATA || [];

    // ─── Referencias DOM ────────────────────────────────────
    const tbody        = document.getElementById('tbody');
    const sinResult    = document.getElementById('sin-resultados');
    const elBusqueda   = document.getElementById('f-busqueda');
    const elEstado     = document.getElementById('f-estado');
    const elMunicipio  = document.getElementById('f-municipio');
    const elCiclo      = document.getElementById('f-solo-activos');
    const elMinAfect   = document.getElementById('f-min-afect');
    const btnLimpiar   = document.getElementById('btn-limpiar');
    const btnPrev      = document.getElementById('btn-prev');
    const btnNext      = document.getElementById('btn-next');
    const pageInfo     = document.getElementById('page-info');
    const elPageSize   = document.getElementById('page-size');
    const modal        = document.getElementById('modal');
    const modalBody    = document.getElementById('modal-body');
    const modalClose   = document.getElementById('modal-close');

    // ─── Utilidades ─────────────────────────────────────────
    const fmt = {
        num: (n) => n.toLocaleString('es-ES'),

        minutos: (min) => {
            if (min == null) return '—';
            if (min < 60) return `${min} min`;
            const h = Math.floor(min / 60);
            const m = min % 60;
            return m ? `${h}h ${m}m` : `${h}h`;
        },

        fechaRelativa: (iso) => {
            if (!iso) return '—';
            const d = new Date(iso);
            const ahora = new Date();
            const diff = (ahora - d) / 1000; // segundos

            if (diff < 60) return 'hace un momento';
            if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
            if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
            if (diff < 604800) return `hace ${Math.floor(diff / 86400)} d`;

            return d.toLocaleDateString('es-ES', {
                day: '2-digit', month: 'short', year: 'numeric',
            });
        },

        fechaCompleta: (iso) => {
            if (!iso) return '—';
            return new Date(iso).toLocaleString('es-ES', {
                day: '2-digit', month: 'long', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        },
    };

    // ─── Filtrado ───────────────────────────────────────────
    function aplicarFiltros() {
        const { busqueda, estado, municipio, ciclo, minAfectaciones } = state.filtros;
        const q = busqueda.trim().toLowerCase();

        return datos.filter((c) => {
            // Búsqueda libre
            if (q) {
                const enCodigo = c.codigo.toLowerCase().includes(q);
                const enDir = (c.direccion || '').toLowerCase().includes(q);
                const enMun = (c.municipio || '').toLowerCase().includes(q);
                if (!enCodigo && !enDir && !enMun) return false;
            }

            // Estado
            if (estado && c.estado !== estado) return false;

            // Municipio
            if (municipio && c.municipio !== municipio) return false;

            // Ciclo
            if (ciclo === 'afectacion' && !c.afectacion_activa) return false;
            if (ciclo === 'servicio' && !c.servicio_activo) return false;
            if (ciclo === 'cerrado' && (c.afectacion_activa || c.servicio_activo)) return false;

            // Mínimo de afectaciones
            if (minAfectaciones > 0 && c.total_afectaciones < minAfectaciones) return false;

            return true;
        });
    }

    // ─── Ordenamiento ───────────────────────────────────────
    function ordenar(arr) {
        const { campo, dir } = state.orden;
        const signo = dir === 'asc' ? 1 : -1;

        return [...arr].sort((a, b) => {
            let va = a[campo];
            let vb = b[campo];

            // Tratar nulos
            if (va == null) va = '';
            if (vb == null) vb = '';

            // Comparación
            if (typeof va === 'number' && typeof vb === 'number') {
                return (va - vb) * signo;
            }
            return String(va).localeCompare(String(vb), 'es', { numeric: true }) * signo;
        });
    }

    // ─── Render ─────────────────────────────────────────────
    function render() {
        const filtrados = aplicarFiltros();
        const ordenados = ordenar(filtrados);
        const total = ordenados.length;

        // Paginación
        const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
        if (state.page > totalPages) state.page = totalPages;
        const inicio = (state.page - 1) * state.pageSize;
        const fin = Math.min(inicio + state.pageSize, total);
        const pagina = ordenados.slice(inicio, fin);

        // Actualizar stats
        document.getElementById('stat-total').textContent = total;

        // Estado vacío
        sinResult.hidden = total > 0;
        tbody.innerHTML = '';

        // Filas
        for (const c of pagina) {
            tbody.appendChild(construirFila(c));
        }

        // Info paginación
        pageInfo.textContent = `Página ${state.page} de ${totalPages} · ${total} resultados`;
        btnPrev.disabled = state.page <= 1;
        btnNext.disabled = state.page >= totalPages;

        // Marcar columna ordenada
        document.querySelectorAll('#tabla-circuitos th.sortable').forEach((th) => {
            th.classList.remove('asc', 'desc');
            if (th.dataset.sort === state.orden.campo) {
                th.classList.add(state.orden.dir);
            }
        });
    }

    function construirFila(c) {
        const tr = document.createElement('tr');
        if (c.estado === 'afectado') tr.classList.add('row-afectado');

        // Duración actual según el ciclo activo
        let duracion = '—';
        let duracionActiva = false;
        if (c.afectacion_activa && c.afectacion_duracion_msg_min != null) {
            duracion = fmt.minutos(c.afectacion_duracion_msg_min);
            duracionActiva = true;
        } else if (c.servicio_activo && c.servicio_duracion_msg_min != null) {
            duracion = fmt.minutos(c.servicio_duracion_msg_min);
        }

        // Último evento
        let eventoHTML = '<span class="municipio">—</span>';
        if (c.ultimo_evento) {
            const tipo = c.ultimo_evento.tipo;
            const preview = escapeHTML(c.ultimo_evento.preview || '');
            eventoHTML = `
                <div class="evento">
                    <span class="evento-tipo ${tipo}">${tipoLabel(tipo)}</span>
                    <span class="evento-preview">${preview}</span>
                </div>
            `;
        }
        const urlDetalle = `/circuitos/c/${encodeURIComponent(c.codigo)}/`;
        tr.innerHTML = `
            <td><a href="${urlDetalle}" class="codigo codigo-link">${escapeHTML(c.codigo)}</a></td>
            <td><span class="badge ${c.estado}">${escapeHTML(c.estado_display)}</span></td>
            <td><span class="municipio">${escapeHTML(c.municipio || '—')}</span></td>
            <td class="num">${fmt.num(c.total_afectaciones)}</td>
            <td class="num">${c.total_horas_afectado}h</td>
            <td class="num duracion-actual ${duracionActiva ? 'activa' : ''}">${duracion}</td>
            <td><span class="fecha-relativa">${fmt.fechaRelativa(c.ultima_mencion)}</span></td>
            <td>${eventoHTML}</td>
        `;
        tr.addEventListener('click', (ev) => {
            // Si el clic fue en un enlace, dejar que navegue
            if (ev.target.closest('a')) return;
            abrirModal(c);
        });
        
        return tr;
    }

    function tipoLabel(tipo) {
        return {
            'afectacion': '⚡ Afectación',
            'restablecimiento': '✅ Restablecimiento',
            'mencion': 'ℹ️ Mención',
        }[tipo] || tipo;
    }

    function escapeHTML(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ─── Modal detalle ──────────────────────────────────────
    function abrirModal(c) {
        const ue = c.ultimo_evento;

        // Bloque del último mensaje
        let mensajeHTML = '<p class="municipio">Sin eventos registrados.</p>';
        if (ue) {
            mensajeHTML = `
                <h3>Último mensaje (${tipoLabel(ue.tipo)})</h3>
                <p class="fecha-relativa">${fmt.fechaCompleta(ue.fecha)}</p>
                <div class="mensaje-completo">${escapeHTML(ue.texto)}</div>
                ${ue.enlace ? `<a class="btn-telegram" href="${ue.enlace}" target="_blank" rel="noopener">Ver en Telegram ↗</a>` : ''}
            `;
        }

        // Campos del ciclo
        const cicloActivo = c.afectacion_activa
            ? `<span class="badge afectado">Afectación activa desde ${fmt.fechaRelativa(c.afectacion_inicio_msg)}</span>`
            : c.servicio_activo
                ? '<span class="badge en_servicio">Servicio activo</span>'
                : '<span class="badge desconocido">Ciclo cerrado</span>';

        modalBody.innerHTML = `
            <h2>${escapeHTML(c.codigo)} <span class="badge ${c.estado}">${escapeHTML(c.estado_display)}</span></h2>

            <div>${cicloActivo}</div>

            <h3>Información general</h3>
            <div class="detalle-grid">
                <div class="campo"><span class="k">Municipio</span><span class="v">${escapeHTML(c.municipio || '—')}</span></div>
                <div class="campo"><span class="k">Subestación</span><span class="v">${escapeHTML(c.subestacion || '—')}</span></div>
                <div class="campo" style="grid-column: 1 / -1;">
                    <span class="k">Dirección</span>
                    <span class="v">${escapeHTML(c.direccion || '—')}</span>
                </div>
            </div>

            <h3>Estadísticas históricas</h3>
            <div class="detalle-grid">
                <div class="campo"><span class="k">Total afectaciones</span><span class="v">${fmt.num(c.total_afectaciones)}</span></div>
                <div class="campo"><span class="k">Horas acumuladas</span><span class="v">${c.total_horas_afectado}h</span></div>
                <div class="campo"><span class="k">Últ. duración afectación</span><span class="v">${fmt.minutos(c.afectacion_duracion_msg_min)}</span></div>
                <div class="campo"><span class="k">Últ. duración servicio</span><span class="v">${fmt.minutos(c.servicio_duracion_msg_min)}</span></div>
                <div class="campo"><span class="k">Última mención</span><span class="v">${fmt.fechaRelativa(c.ultima_mencion)}</span></div>
            </div>

            ${mensajeHTML}
        `;

        modal.hidden = false;
    }

    function cerrarModal() {
        modal.hidden = true;
        modalBody.innerHTML = '';
    }

    // ─── Event listeners ────────────────────────────────────
    elBusqueda.addEventListener('input', (e) => {
        state.filtros.busqueda = e.target.value;
        state.page = 1;
        render();
    });

    elEstado.addEventListener('change', (e) => {
        state.filtros.estado = e.target.value;
        state.page = 1;
        render();
    });

    elMunicipio.addEventListener('change', (e) => {
        state.filtros.municipio = e.target.value;
        state.page = 1;
        render();
    });

    elCiclo.addEventListener('change', (e) => {
        state.filtros.ciclo = e.target.value;
        state.page = 1;
        render();
    });

    elMinAfect.addEventListener('input', (e) => {
        state.filtros.minAfectaciones = parseInt(e.target.value, 10) || 0;
        state.page = 1;
        render();
    });

    btnLimpiar.addEventListener('click', () => {
        elBusqueda.value = '';
        elEstado.value = '';
        elMunicipio.value = '';
        elCiclo.value = '';
        elMinAfect.value = '0';
        state.filtros = { busqueda: '', estado: '', municipio: '', ciclo: '', minAfectaciones: 0 };
        state.page = 1;
        render();
    });

    document.querySelectorAll('#tabla-circuitos th.sortable').forEach((th) => {
        th.addEventListener('click', () => {
            const campo = th.dataset.sort;
            if (state.orden.campo === campo) {
                state.orden.dir = state.orden.dir === 'asc' ? 'desc' : 'asc';
            } else {
                state.orden.campo = campo;
                state.orden.dir = 'asc';
            }
            render();
        });
    });

    btnPrev.addEventListener('click', () => {
        if (state.page > 1) { state.page--; render(); }
    });
    btnNext.addEventListener('click', () => {
        state.page++; render();
    });

    elPageSize.addEventListener('change', (e) => {
        state.pageSize = parseInt(e.target.value, 10);
        state.page = 1;
        render();
    });

    modalClose.addEventListener('click', cerrarModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) cerrarModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.hidden) cerrarModal();
    });

    // ─── Arranque ───────────────────────────────────────────
    render();
})();