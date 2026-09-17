/**
 * Dashboard de métricas — carga AJAX de todas las secciones
 * y renderizado con Chart.js.
 */

(function () {
    'use strict';

    const URLS = window.METRICAS_URLS || {};

    // ═══════════════════════════════════════════════════════════
    // UTILIDADES
    // ═══════════════════════════════════════════════════════════
    const fmt = {
        num: (n) => Number(n || 0).toLocaleString('es-ES'),

        min: (m) => {
            if (m == null) return '—';
            const n = Number(m);
            if (!isFinite(n) || n < 0) return '—';
            if (n < 60) return `${Math.round(n)} min`;
            const h = Math.floor(n / 60);
            const r = Math.round(n % 60);
            return r > 0 ? `${h}h ${r}m` : `${h}h`;
        },

        horas: (h) => {
            const n = Number(h || 0);
            if (n < 10) return n.toFixed(1);
            return Math.round(n);
        },

        pct: (p) => `${Number(p || 0).toFixed(1)}%`,

        pad2: (n) => String(n).padStart(2, '0'),
    };

    const escapeHTML = (s) => String(s || '').replace(
        /[&<>"']/g,
        (c) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[c]),
    );

    // ═══════════════════════════════════════════════════════════
    // FETCH HELPER
    // ═══════════════════════════════════════════════════════════
    async function fetchData(key) {
        const url = URLS[key];
        if (!url) throw new Error(`URL no definida: ${key}`);
        const resp = await fetch(url, {
            headers: { Accept: 'application/json' },
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        if (!json.ok) throw new Error(json.error || 'Error desconocido');
        return json.data;
    }

    function ocultarLoading(id) {
        const el = document.querySelector(`.loading[data-for="${id}"]`);
        if (el) el.classList.add('oculto');
    }

    function marcarError(id, msg = 'Error') {
        const el = document.querySelector(`.loading[data-for="${id}"]`);
        if (el) {
            el.textContent = msg;
            el.classList.remove('oculto');
            el.style.color = 'var(--rojo)';
        }
    }

    // ═══════════════════════════════════════════════════════════
    // CONFIGURACIÓN GLOBAL CHART.JS
    // ═══════════════════════════════════════════════════════════
    if (window.Chart) {
        Chart.defaults.font.family = "'-apple-system','Segoe UI',Roboto,sans-serif";
        Chart.defaults.font.size = 11;
        Chart.defaults.color = '#666';
        Chart.defaults.plugins.legend.display = false;
        Chart.defaults.maintainAspectRatio = false;
    }

    // Almacén de charts para poder destruirlos al refrescar
    const charts = {};

    function crearChart(id, config) {
        const ctx = document.getElementById(id);
        if (!ctx) return;
        if (charts[id]) charts[id].destroy();
        charts[id] = new Chart(ctx, config);
    }

    // ═══════════════════════════════════════════════════════════
    // 1. CHART: ACTIVOS POR HORA
    // ═══════════════════════════════════════════════════════════
    async function renderActivosHora() {
        const id = 'chart-activos-hora';
        try {
            const data = await fetchData('activos_hora');

            crearChart(id, {
                type: 'line',
                data: {
                    labels: data.map((d) => d.hora),
                    datasets: [{
                        label: 'Circuitos afectados',
                        data: data.map((d) => d.total),
                        borderColor: '#1976d2',
                        backgroundColor: 'rgba(25,118,210,0.15)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        borderWidth: 2,
                    }],
                },
                options: {
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: (items) => `Hora: ${items[0].label}`,
                                label: (item) => `${item.parsed.y} circuitos afectados`,
                            },
                        },
                    },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                        x: {
                            ticks: {
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 12,
                            },
                        },
                    },
                },
            });
            ocultarLoading(id);
        } catch (e) {
            marcarError(id, 'Error al cargar');
            console.error(e);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 2. CHART: MEDIA DIARIA
    // ═══════════════════════════════════════════════════════════
    async function renderMediaDiaria() {
        const id = 'chart-media-diaria';
        try {
            const data = await fetchData('media_diaria');

            crearChart(id, {
                type: 'bar',
                data: {
                    labels: data.map((d) => d.fecha),
                    datasets: [{
                        label: 'Media diaria',
                        data: data.map((d) => d.total),
                        backgroundColor: 'rgba(239,108,0,0.7)',
                        borderColor: '#ef6c00',
                        borderWidth: 1,
                        borderRadius: 4,
                    }],
                },
                options: {
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: (item) => `${item.parsed.y} circuitos (med.)`,
                            },
                        },
                    },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                        x: { ticks: { maxRotation: 0 } },
                    },
                },
            });
            ocultarLoading(id);
        } catch (e) {
            marcarError(id, 'Error al cargar');
            console.error(e);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 3. ROTACIÓN MEDIA (duración de afectaciones)
    // ═══════════════════════════════════════════════════════════
    async function renderRotacion() {
        try {
            const data = await fetchData('rotacion');
            const cont = document.getElementById('rotacion-media');
            if (!cont) return;

            cont.querySelectorAll('.stat-pair-valor').forEach((el) => {
                const key = el.dataset.key;
                el.textContent = data[key] != null ? fmt.min(data[key]) : '—';
            });

            const nota = document.getElementById('rotacion-muestras');
            if (nota) {
                nota.textContent =
                    `Basado en ${data.muestras || 0} ciclos cerrados. ` +
                    `Los ciclos abiertos y los de duración > 72h se excluyen.`;
            }
        } catch (e) {
            console.error('Error rotación:', e);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 4. HEATMAP POR HORA DEL DÍA
    // ═══════════════════════════════════════════════════════════
    async function renderHeatmap() {
        try {
            const data = await fetchData('heatmap');
            const cont = document.getElementById('heatmap-hora');
            if (!cont) return;

            const max = Math.max(...data.map((d) => d.total), 1);

            cont.innerHTML = data.map((d) => {
                const intensidad = d.total / max;
                const bg = `rgba(211,47,47,${0.15 + intensidad * 0.85})`;
                const textColor = intensidad > 0.5 ? 'white' : '#333';
                return `
                    <div class="heat-cell"
                         style="background:${bg}; color:${textColor};"
                         title="${fmt.pad2(d.hora)}:00 → ${d.total} afectaciones">
                        <span class="heat-hora">${fmt.pad2(d.hora)}</span>
                        <span class="heat-valor">${d.total}</span>
                    </div>
                `;
            }).join('');
        } catch (e) {
            console.error('Error heatmap:', e);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 5. PREDICCIÓN
    // ═══════════════════════════════════════════════════════════
    async function renderPrediccion() {
        try {
            const data = await fetchData('prediccion');
            const cont = document.getElementById('prediccion');
            if (!cont) return;

            if (!data.length) {
                cont.innerHTML =
                    '<li class="vacio">Sin patrones suficientes.</li>';
                return;
            }

            cont.innerHTML = data.map((p) => `
                <li title="${p.dias_coincidentes} de los últimos ${p.dias_analizados} días">
                    <a href="/circuitos/c/${encodeURIComponent(p.codigo)}/"
                       class="codigo-inline">
                        ${escapeHTML(p.codigo)}
                    </a>
                    <span class="text-muted">${escapeHTML(p.municipio || '—')}</span>
                    <span class="badge-score medio">${p.probabilidad}%</span>
                </li>
            `).join('');
        } catch (e) {
            console.error('Error predicción:', e);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 6. TENDENCIA SEMANAL
    // ═══════════════════════════════════════════════════════════
    async function renderTendencia() {
        try {
            const data = await fetchData('tendencia');
            const cont = document.getElementById('tendencia');
            if (!cont) return;

            cont.querySelector('[data-key="esta_semana"]').textContent =
                fmt.num(data.esta_semana);
            cont.querySelector('[data-key="semana_anterior"]').textContent =
                fmt.num(data.semana_anterior);

            const arrow = document.getElementById('tendencia-arrow');
            const pct = data.cambio_pct;
            arrow.textContent = data.mejora
                ? `↓ ${Math.abs(pct)}%`
                : `↑ ${pct}%`;
            arrow.className = 'tendencia-arrow ' +
                (data.mejora ? 'mejora' : 'empeora');

            // Texto explicativo
            const texto = document.getElementById('tendencia-texto');
            if (texto) {
                const diff = Math.abs(data.esta_semana - data.semana_anterior);
                if (data.mejora) {
                    texto.innerHTML =
                        `✅ <strong>${diff}</strong> afectaciones menos que ` +
                        `la semana anterior. La situación <strong>mejora</strong>.`;
                    texto.className = 'tendencia-texto mejora';
                } else {
                    texto.innerHTML =
                        `⚠️ <strong>${diff}</strong> afectaciones más que ` +
                        `la semana anterior. La situación <strong>empeora</strong>.`;
                    texto.className = 'tendencia-texto empeora';
                }
            }

            // KPI de cabecera
            const kpi = document.querySelector('#kpi-tendencia .kpi-mini-valor');
            if (kpi) {
                kpi.textContent = (data.mejora ? '↓' : '↑') +
                    Math.abs(pct) + '%';
                kpi.style.color = data.mejora ? 'var(--verde)' : 'var(--rojo)';
            }
        } catch (e) {
            console.error('Error tendencia:', e);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // HELPERS PARA TABLAS
    // ═══════════════════════════════════════════════════════════
    function renderTabla(id, filas, plantilla, colspan = 6) {
        const tbody = document.querySelector(`#${id} tbody`);
        if (!tbody) return;
        if (!filas.length) {
            tbody.innerHTML =
                `<tr><td colspan="${colspan}" class="vacio">Sin datos.</td></tr>`;
            return;
        }
        tbody.innerHTML = filas.map(plantilla).join('');
    }

    const linkCircuito = (codigo) =>
        `<a href="/circuitos/c/${encodeURIComponent(codigo)}/"
            class="codigo-inline">${escapeHTML(codigo)}</a>`;

    // ═══════════════════════════════════════════════════════════
    // 7. TABLA MUNICIPIOS
    // ═══════════════════════════════════════════════════════════
    async function renderMunicipios() {
        try {
            const data = await fetchData('municipios');
            renderTabla('tabla-municipios', data, (m) => `
                <tr>
                    <td><strong>${escapeHTML(m.municipio)}</strong></td>
                    <td class="num">${fmt.num(m.total_circuitos)}</td>
                    <td class="num text-rojo">${fmt.num(m.afectados_ahora)}</td>
                    <td class="num">${fmt.horas(m.horas_totales)}h</td>
                </tr>
            `);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 8. TABLA ESTABILIDAD
    // ═══════════════════════════════════════════════════════════
    async function renderEstabilidad() {
        try {
            const data = await fetchData('estabilidad');
            renderTabla('tabla-estabilidad', data, (c) => {
                const cls = c.score >= 70 ? 'alto'
                    : (c.score >= 40 ? 'medio' : 'bajo');
                return `
                    <tr>
                        <td>${linkCircuito(c.codigo)}</td>
                        <td class="num">${fmt.pct(c.disponibilidad)}</td>
                        <td class="num">${fmt.num(c.ciclos)}</td>
                        <td class="num">
                            <span class="badge-score ${cls}">${c.score}</span>
                        </td>
                    </tr>
                `;
            }, 4);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 9. TABLA MÁS HORAS SIN SERVICIO
    // ═══════════════════════════════════════════════════════════
    async function renderMasSinServicio() {
        try {
            const data = await fetchData('mas_horas_sin');
            renderTabla('tabla-mas-sin', data, (c) => `
                <tr>
                    <td>${linkCircuito(c.codigo)}</td>
                    <td class="num duracion larga">
                        ${fmt.horas(c.total_horas)}h
                    </td>
                </tr>
            `, 2);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 10. TABLA MÁS HORAS DE SERVICIO
    // ═══════════════════════════════════════════════════════════
    async function renderMasServicio() {
        try {
            const data = await fetchData('mas_horas_serv');
            renderTabla('tabla-mas-serv', data, (c) => `
                <tr>
                    <td>${linkCircuito(c.codigo)}</td>
                    <td class="num duracion corta">
                        ${fmt.horas(c.horas_servicio)}h
                    </td>
                </tr>
            `, 2);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 11. TABLA MAYOR ROTACIÓN
    // ═══════════════════════════════════════════════════════════
    async function renderMayorRotacion() {
        try {
            const data = await fetchData('mayor_rotacion');
            renderTabla('tabla-rotacion', data, (c) => `
                <tr>
                    <td>${linkCircuito(c.circuito__codigo)}</td>
                    <td class="num"><strong>${fmt.num(c.veces)}</strong></td>
                </tr>
            `, 2);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 12. TABLA MTTR
    // ═══════════════════════════════════════════════════════════
    async function renderMTTR() {
        try {
            const data = await fetchData('mttr');
            renderTabla('tabla-mttr', data, (c) => `
                <tr>
                    <td>${linkCircuito(c.codigo)}</td>
                    <td class="text-muted">${escapeHTML(c.municipio || '—')}</td>
                    <td class="num duracion">${fmt.horas(c.mttr_horas)}h</td>
                    <td class="num text-muted">${c.muestras}</td>
                </tr>
            `, 4);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 13. TABLA TIEMPO ENTRE AFECTACIONES
    // ═══════════════════════════════════════════════════════════
    async function renderTiempoEntre() {
        try {
            const data = await fetchData('tiempo_entre');
            renderTabla('tabla-tiempo-entre', data, (c) => `
                <tr>
                    <td>${linkCircuito(c.codigo)}</td>
                    <td class="num duracion ${c.tiempo_medio_min < 120 ? 'larga' : ''}">
                        ${fmt.min(c.tiempo_medio_min)}
                    </td>
                    <td class="num text-muted">${c.muestras}</td>
                </tr>
            `, 3);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 14. TABLA DISPONIBILIDAD
    // ═══════════════════════════════════════════════════════════
    async function renderDisponibilidad() {
        try {
            const data = await fetchData('disponibilidad');
            renderTabla('tabla-disponibilidad', data, (c) => {
                const cls = c.disponibilidad >= 80 ? 'alto'
                    : (c.disponibilidad >= 50 ? 'medio' : 'bajo');
                return `
                    <tr>
                        <td>${linkCircuito(c.codigo)}</td>
                        <td class="text-muted">${escapeHTML(c.municipio || '—')}</td>
                        <td class="num">
                            <span class="badge-score ${cls}">
                                ${fmt.pct(c.disponibilidad)}
                            </span>
                        </td>
                    </tr>
                `;
            }, 3);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 15. TABLA CRÓNICOS
    // ═══════════════════════════════════════════════════════════
    async function renderCronicos() {
        try {
            const data = await fetchData('cronicos');
            renderTabla('tabla-cronicos', data, (c) => `
                <tr>
                    <td>${linkCircuito(c.codigo)}</td>
                    <td class="num">
                        <span class="badge-score bajo">
                            ${fmt.pct(c.disponibilidad)}
                        </span>
                    </td>
                    <td class="num">${fmt.num(c.ciclos)}</td>
                    <td class="num duracion">${fmt.horas(c.horas_afectado)}h</td>
                </tr>
            `, 4);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 16. LISTA DAF
    // ═══════════════════════════════════════════════════════════
    async function renderDAF() {
        try {
            const data = await fetchData('daf');
            const cont = document.getElementById('lista-daf');
            if (!cont) return;

            if (!data.length) {
                cont.innerHTML =
                    '<li class="vacio">Sin circuitos DAF activos esta semana.</li>';
                return;
            }

            cont.innerHTML = data.map((d) => `
                <li>
                    ${linkCircuito(d.codigo)}
                    <span class="text-muted">${escapeHTML(d.municipio || '—')}</span>
                    <span class="text-muted" style="font-size:11px">
                        ${d.desde} → ${d.hasta}
                    </span>
                </li>
            `).join('');
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 17. LISTA SIN ROTACIÓN
    // ═══════════════════════════════════════════════════════════
    async function renderSinRotacion() {
        try {
            const data = await fetchData('sin_rotacion');
            const cont = document.getElementById('lista-sin-rotacion');
            if (!cont) return;

            if (!data.length) {
                cont.innerHTML =
                    '<li class="vacio">Todos los circuitos tuvieron eventos.</li>';
                return;
            }

            cont.innerHTML = data.slice(0, 30).map((c) => `
                <li>
                    ${linkCircuito(c.codigo)}
                    <span class="text-muted">${escapeHTML(c.municipio || '—')}</span>
                    <span class="badge ${c.estado}">${c.estado}</span>
                </li>
            `).join('');
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 18. TABLA RANKING USUARIOS
    // ═══════════════════════════════════════════════════════════
    async function renderRanking() {
        try {
            const data = await fetchData('ranking');
            renderTabla('tabla-ranking', data, (u) => `
                <tr>
                    <td><strong>${escapeHTML(u.username)}</strong></td>
                    <td class="num">${fmt.num(u.vinculados)}</td>
                    <td class="num">${fmt.num(u.reportes)}</td>
                    <td class="num">
                        <span class="badge-score alto">${u.puntos}</span>
                    </td>
                </tr>
            `, 4);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 19. TABLA ALERTAS HISTÓRICAS
    // ═══════════════════════════════════════════════════════════
    async function renderAlertas() {
        try {
            const data = await fetchData('alertas');
            renderTabla('tabla-alertas', data, (a) => `
                <tr>
                    <td><strong>${escapeHTML(a.titulo)}</strong></td>
                    <td class="text-muted">${escapeHTML(a.tipo)}</td>
                    <td class="text-muted">${escapeHTML(a.inicio)}</td>
                    <td class="num duracion">${fmt.horas(a.duracion_h)}h</td>
                    <td>
                        ${a.activo
                            ? '<span class="badge afectado">Activa</span>'
                            : '<span class="badge en_servicio">Cerrada</span>'}
                    </td>
                </tr>
            `, 5);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // 20. TABLA DURACIÓN POR USUARIO
    // ═══════════════════════════════════════════════════════════
    async function renderDuracionUsuarios() {
        try {
            const data = await fetchData('duracion_usuarios');
            renderTabla('tabla-duracion-usuarios', data, (u) => `
                <tr>
                    <td><strong>${escapeHTML(u.username)}</strong></td>
                    <td class="num">${fmt.num(u.circuitos)}</td>
                    <td class="num duracion larga">
                        ${fmt.horas(u.horas_afectado)}h
                    </td>
                </tr>
            `, 3);
        } catch (e) { console.error(e); }
    }

    // ═══════════════════════════════════════════════════════════
    // ORQUESTADOR
    // ═══════════════════════════════════════════════════════════
    async function cargarTodo() {
        const inicio = performance.now();

        // KPIs y charts primero (rápidos)
        await Promise.allSettled([
            renderTendencia(),
            renderActivosHora(),
            renderMediaDiaria(),
            renderRotacion(),
            renderHeatmap(),
        ]);

        // El resto en paralelo
        await Promise.allSettled([
            renderPrediccion(),
            renderMunicipios(),
            renderEstabilidad(),
            renderMasSinServicio(),
            renderMasServicio(),
            renderMayorRotacion(),
            renderMTTR(),
            renderTiempoEntre(),
            renderDisponibilidad(),
            renderCronicos(),
            renderDAF(),
            renderSinRotacion(),
            renderRanking(),
            renderAlertas(),
            renderDuracionUsuarios(),
        ]);

        const duracion = ((performance.now() - inicio) / 1000).toFixed(1);
        const el = document.getElementById('ultima-actualizacion');
        if (el) {
            el.textContent = new Date().toLocaleTimeString('es-ES');
            el.title = `Cargado en ${duracion}s`;
        }

        console.log(`✅ Dashboard cargado en ${duracion}s`);
    }

    // ═══════════════════════════════════════════════════════════
    // BOTÓN REFRESH
    // ═══════════════════════════════════════════════════════════
    function bindRefresh() {
        const btn = document.getElementById('btn-refresh');
        if (!btn) return;

        btn.addEventListener('click', async () => {
            btn.disabled = true;
            btn.textContent = '🔄 Cargando…';

            // Resetear loadings
            document.querySelectorAll('.loading').forEach((el) => {
                el.classList.remove('oculto');
                el.textContent = 'Cargando…';
                el.style.color = '';
            });

            await cargarTodo();

            btn.disabled = false;
            btn.textContent = '🔄 Actualizar';
        });
    }

    // ═══════════════════════════════════════════════════════════
    // INICIALIZACIÓN
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', () => {
        bindRefresh();
        cargarTodo();
    });
})();