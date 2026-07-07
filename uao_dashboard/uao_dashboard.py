"""
UAO Fútbol Sala — Dashboard de Rendimiento Deportivo
=====================================================
  1. Cambia FILE_PATH con la ruta de tu Excel
  2. Ejecuta:  python uao_dashboard.py
  3. Abre:     http://localhost:8050
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update, ALL
import dash_bootstrap_components as dbc
import json

# ══════════════════════════════════════════
# ⚠️  CAMBIA ESTA LÍNEA CON TU RUTA ⚠️
# ══════════════════════════════════════════
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# ══════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════
def load_data(path):
    # ── Nombres desde "Datos generales" ──
    dg = pd.read_excel(path, sheet_name='Datos generales', header=None)
    dg = dg.iloc[1:, [1]].copy()
    dg.columns = ['Nombre']
    dg = dg.dropna()
    dg['Nombre'] = dg['Nombre'].astype(str).str.strip()

    
    # ── Función z-score ──
    def zscore_col(s):
        s     = pd.to_numeric(s, errors='coerce')
        media = s.mean()
        std   = s.std()
        if std == 0 or pd.isna(std):
            return pd.Series([0.0] * len(s), index=s.index)
        return ((s - media) / std).round(3)

    # ── Velocidad (hoja "Velocidad") ──
    dv = pd.read_excel(path, sheet_name='Velocidad', header=0)
    dv.columns = [str(c).strip() for c in dv.columns]
    dv = dv[dv['Nombre'].astype(str).str.startswith('UAO_')].copy()
    dv['Nombre'] = dv['Nombre'].astype(str).str.strip()
    # z-score por distancia * -1 (menos tiempo = mejor), luego TSA
    dv['Z_10m_py'] = zscore_col(dv['sprint_10m_p1']) * -1
    dv['Z_20m_py'] = zscore_col(dv['sprint_20m_p1']) * -1
    dv['Z_30m_py'] = zscore_col(dv['sprint_30m_p1']) * -1
    dv['Vel_Z']    = dv[['Z_10m_py', 'Z_20m_py', 'Z_30m_py']].mean(axis=1).round(3)
    dv = dv[['Nombre', 'sprint_10m_p1', 'sprint_20m_p1', 'sprint_30m_p1', 'Vel_Z']]

    # ── 5-10-5 (hoja "5-10-5") ──
    d5 = pd.read_excel(path, sheet_name='5-10-5', header=0)
    d5 = d5[d5['Nombre'].astype(str).str.startswith('UAO_')].copy()
    d5['Nombre'] = d5['Nombre'].astype(str).str.strip()
    # Columnas por posición: col 1=tiempo intento 1, col 5=intento 2, col 9=intento 3
    cols_d5 = d5.columns.tolist()
    t1_col  = cols_d5[2]   # Tiempo promedio intento 1
    t2_col  = cols_d5[6]   # Tiempo promedio intento 2
    t3_col  = cols_d5[10]   # Tiempo promedio intento 3
    d5['Z_510_1'] = zscore_col(d5[t1_col]) * -1
    d5['Z_510_2'] = zscore_col(d5[t2_col]) * -1
    d5['Z_510_3'] = zscore_col(d5[t3_col]) * -1
    d5['Ag_Z']    = d5[['Z_510_1', 'Z_510_2', 'Z_510_3']].mean(axis=1).round(3)
    d5 = d5[['Nombre', t1_col, t2_col, t3_col, 'Ag_Z']]
    d5.columns = ['Nombre', 't510_1', 't510_2', 't510_3', 'Ag_Z']

    # ── Stardrill (hoja "Stardrill") ──
    dsd = pd.read_excel(path, sheet_name='Stardrill', header=0)
    dsd = dsd[dsd['Nombre'].astype(str).str.startswith('UAO_')].copy()
    dsd['Nombre'] = dsd['Nombre'].astype(str).str.strip()
    cols_dsd = dsd.columns.tolist()
    s1_col   = cols_dsd[2]    # Tiempo promedio intento 1
    s2_col   = cols_dsd[15]   # Tiempo promedio intento 2
    dsd['Z_sd_1']  = zscore_col(dsd[s1_col]) * -1
    dsd['Z_sd_2']  = zscore_col(dsd[s2_col]) * -1
    dsd['Star_Z']  = dsd[['Z_sd_1', 'Z_sd_2']].mean(axis=1).round(3)
    dsd = dsd[['Nombre', s1_col, s2_col, 'Star_Z']]
    dsd.columns = ['Nombre', 'sd_t1', 'sd_t2', 'Star_Z']

    # ── Merge todo con datos generales ──
    df = dg.copy()
    df = df[df['Nombre'].str.startswith('UAO_')].reset_index(drop=True)
    df = df.merge(dv,  on='Nombre', how='left')
    df = df.merge(d5,  on='Nombre', how='left')
    df = df.merge(dsd, on='Nombre', how='left')

    # ── Overall Z y nivel ──
    df['Overall_Z'] = df[['Vel_Z', 'Ag_Z', 'Star_Z']].mean(axis=1).round(3)

    def to_100(s):
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series([50.0] * len(s), index=s.index)
        return ((s - mn) / (mx - mn) * 100).round(1)

    df['Vel_N']   = to_100(df['Vel_Z'])
    df['Ag_N']    = to_100(df['Ag_Z'])
    df['Star_N']  = to_100(df['Star_Z'])
    df['Overall'] = df[['Vel_N', 'Ag_N', 'Star_N']].mean(axis=1).round(1)

    def nivel(s):
        if s >= 66: return 'Alto'
        if s >= 33: return 'Medio'
        return 'Bajo'
    df['Nivel'] = df['Overall'].apply(nivel)

    # Lee desde fila 0 para tomar los nombres reales de columna
    # ── Saltos desde "Saltos" ──
    # header=0 usa fila 0 como nombres de columna (tiene TODAS las métricas _1 _2 _3)
    # Los datos de jugadores están en filas 1-27, se filtran por UAO_
    ds = pd.read_excel(path, sheet_name='Saltos', header=0)
    ds = ds[ds['Nombre'].astype(str).str.startswith('UAO_')].copy()
    ds['Nombre'] = ds['Nombre'].astype(str).str.strip()
    ds = ds.reset_index(drop=True)

    # ── Función: promedia los intentos _1, _2, _3 de un patrón ──
    def prom_intentos(ds_local, patron):
        """Promedia columnas que coincidan con patron + número de intento."""
        cols = [c for c in ds_local.columns
                if str(c).startswith(patron) and str(c)[-1].isdigit()]
        if not cols:
            return pd.Series([np.nan] * len(ds_local), index=ds_local.index)
        return ds_local[cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)

    # ── Función: calcula z-score del grupo ──
    def zscore_grupo(serie):
        """z = (valor - media) / desviación estándar del grupo."""
        media = serie.mean()
        std   = serie.std()
        if std == 0 or pd.isna(std):
            return pd.Series([0.0] * len(serie), index=serie.index)
        return ((serie - media) / std).round(3)

    # ── Promediar intentos crudos (_1, _2, _3) ──
    # CMJ
    ds['cmj_altura_raw']     = prom_intentos(ds, 'jump_height_cmj_')
    ds['cmj_vuelo_raw']      = prom_intentos(ds, 'flight_time_cmj_')
    ds['cmj_potencia_raw']   = prom_intentos(ds, 'avg_propulsive_power_cmj_')
    ds['cmj_aterrizaje_raw'] = prom_intentos(ds, 'peak_landing_force_cmj_')
    ds['cmj_rsi_raw']        = prom_intentos(ds, 'RSI_cmj_')

    # SJ
    ds['sj_altura_raw']     = prom_intentos(ds, 'jump_height_sj_')
    ds['sj_vuelo_raw']      = prom_intentos(ds, 'flight_time_sj_')
    ds['sj_potencia_raw']   = prom_intentos(ds, 'avg_propulsive_power_sj_')
    ds['sj_aterrizaje_raw'] = prom_intentos(ds, 'peak_landing_force_sj_')

    # DJ
    ds['dj_altura_raw']     = prom_intentos(ds, 'jump_height_dj_')
    ds['dj_vuelo_raw']      = prom_intentos(ds, 'flight_time_dj_')
    ds['dj_potencia_raw']   = prom_intentos(ds, 'avg_propulsive_power_dj_')
    ds['dj_aterrizaje_raw'] = prom_intentos(ds, 'peak_braking_force_dj_')
    ds['dj_rsi_raw']        = prom_intentos(ds, 'RSI__dj_')

    # ── Calcular z-score automático por grupo ──
    raw_cols = [
        'cmj_altura_raw', 'cmj_vuelo_raw', 'cmj_potencia_raw',
        'cmj_aterrizaje_raw', 'cmj_rsi_raw',
        'sj_altura_raw', 'sj_vuelo_raw', 'sj_potencia_raw', 'sj_aterrizaje_raw',
        'dj_altura_raw', 'dj_vuelo_raw', 'dj_potencia_raw',
        'dj_aterrizaje_raw', 'dj_rsi_raw',
    ]
    for col in raw_cols:
        z_col = col.replace('_raw', '_z')
        z = zscore_grupo(pd.to_numeric(ds[col], errors='coerce'))
        ds[z_col] = (-z).round(3)

    # ── Merge con df principal ──
    keep = ['Nombre'] + raw_cols + [c.replace('_raw', '_z') for c in raw_cols]
    ds   = ds[keep].copy()
    ds['Nombre'] = ds['Nombre'].astype(str).str.strip()
    df['Nombre'] = df['Nombre'].astype(str).str.strip()

    df = df.merge(ds, on='Nombre', how='left')
    df = df.sort_values('Overall', ascending=False).reset_index(drop=True)
    return df


DEFAULT_FILE = os.path.join(UPLOAD_FOLDER, "datos.xlsx")

try:
    if os.path.exists(DEFAULT_FILE):
        df = load_data(DEFAULT_FILE)
        print("Excel cargado.")
    else:
        raise FileNotFoundError

    print(f"✅  {len(df)} deportistas cargados")
except Exception as e:
    print(f"⚠️  Excel no encontrado: {e}\n   Usando datos de ejemplo.")
    np.random.seed(42)
    ids = [f'UAO_{i:03d}' for i in range(1, 28)]
    df  = pd.DataFrame({
        'Nombre':    ids,
        'Velocidad': np.random.randn(27),
        '5_10_5':    np.random.randn(27),
        'StarDrill': np.random.randn(27),
    })
    def to100(s):
        mn, mx = s.min(), s.max()
        return ((s - mn) / (mx - mn) * 100).round(1)
    df['Vel_N']   = to100(df['Velocidad'])
    df['Ag_N']    = to100(df['5_10_5'])
    df['Star_N']  = to100(df['StarDrill'])
    df['Overall'] = df[['Vel_N', 'Ag_N', 'Star_N']].mean(axis=1).round(1)
    df['Overall_Z'] = df[['Velocidad', '5_10_5', 'StarDrill']].mean(axis=1).round(3)
    df['Nivel']   = df['Overall'].apply(
        lambda s: 'Alto' if s >= 66 else ('Medio' if s >= 33 else 'Bajo'))
    for k in ['cmj_rfd_exc', 'cmj_altura', 'cmj_potencia', 'cmj_aterrizaje',
              'sj_rfd_conc', 'sj_altura',  'sj_potencia',  'sj_aterrizaje',
              'dj_altura',   'dj_rsi',     'dj_impacto',   'dj_aterrizaje', 'dj_tiempo']:
        df[k] = np.random.uniform(0.2, 0.8, 27).round(3)
    df = df.sort_values('Overall', ascending=False).reset_index(drop=True)

ALL_IDS = df['Nombre'].tolist()

# ══════════════════════════════════════════
# PALETA
# ══════════════════════════════════════════
BG    = '#F4F5F8'
SURF  = '#FFFFFF'
SURF2 = '#EEF0F5'
SURF3 = '#E4E7EE'
TEXT  = "#0A0B0F"
MUTED = "#030303"
FAINT = "#030303"
HOT   = "#BE0202"
WARM  = "#FFF127"
COOL  = '#1D4ED8'
TEAL  = "#009C22"
GOLD  = "#FFDD1F"


RADAR_COLORS = [
    '#3B82F6','#E8402A','#14B8A6','#F5C542','#8B5CF6',
    '#F28C38','#10B981','#06B6D4','#A855F7','#F97316',
    '#22C55E','#EC4899','#0EA5E9','#84CC16','#F59E0B',
    '#6366F1','#EF4444','#34D399','#FB923C','#818CF8',
    '#4ADE80','#F472B6','#38BDF8','#A3E635','#FCD34D',
    '#C084FC','#67E8F9',
]

def nc(nivel):
    return TEAL if nivel == 'Alto' else GOLD if nivel == 'Medio' else HOT

def hex_to_rgba(hex_color, alpha=0.73):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'

PLOT_BASE = dict(
    paper_bgcolor=SURF, plot_bgcolor=SURF,
    font=dict(color=TEXT, family='Inter,sans-serif', size=12),
    margin=dict(l=8, r=8, t=28, b=8),
)

def sparkline_fig(values, color, height=28):
    """Genera una mini figura Plotly de línea de tendencia (sin ejes) para stat cards."""
    vals = list(values)
    if len(vals) < 2:
        vals = [0, 0]
    fig = go.Figure(go.Scatter(
        x=list(range(len(vals))), y=vals, mode='lines+markers',
        line=dict(color=color, width=1.8, shape='spline'),
        marker=dict(size=[0] * (len(vals) - 1) + [5], color=color),
        hoverinfo='skip',
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def build_highlight_traces(sub_full, highlights):
    """
    Devuelve una lista de filas especiales (mejor, promedio, peor)
    para agregar al radar de rendimiento físico.
    sub_full: df completo del equipo (todos los jugadores).
    """
    traces = []

    if 'best' in highlights:
        best_row = sub_full.loc[sub_full['Overall_Z'].idxmax()].copy()
        best_row['Nombre'] = f'★ Mejor ({best_row["Nombre"]})'
        traces.append(('best', best_row))

    if 'avg' in highlights:
        avg_series = pd.Series({
            'Nombre':  'Promedio grupo',
            'Vel_Z':   sub_full['Vel_Z'].mean(),
            'Ag_Z':    sub_full['Ag_Z'].mean(),
            'Star_Z':  sub_full['Star_Z'].mean(),
        })
        traces.append(('avg', avg_series))

    if 'worst' in highlights:
        worst_row = sub_full.loc[sub_full['Overall_Z'].idxmin()].copy()
        worst_row['Nombre'] = f'▼ Peor ({worst_row["Nombre"]})'
        traces.append(('worst', worst_row))

    return traces

# ══════════════════════════════════════════
# FIGURAS — RENDIMIENTO
# ══════════════════════════════════════════
def fig_radar(sub, highlight_traces=None):
    labels  = ['Velocidad', '5-10-5', 'Star Drill']
    cols    = ['Vel_Z', 'Ag_Z', 'Star_Z']
    offset  = 3.5
    axis_max = 7.0
    tick_vals = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
    tick_text = ['z=-3', 'z=-2', 'z=-1', 'z=0', 'z=+1', 'z=+2', 'z=+3']

    fig = go.Figure()
    for i, row in sub.iterrows():
        col  = RADAR_COLORS[list(sub.index).index(i) % len(RADAR_COLORS)]
        hex_ = col.lstrip('#')
        r, g, b = int(hex_[:2], 16), int(hex_[2:4], 16), int(hex_[4:], 16)

        r_vals = [row[c] + offset for c in cols]
        hover_lines = [f"<b>{lbl}</b>: z={row[c]:+.3f}" for lbl, c in zip(labels, cols)]

        fig.add_trace(go.Scatterpolar(
            r=r_vals,
            theta=labels,
            fill='toself', name=row['Nombre'],
            line=dict(color=col, width=2.5 if len(sub) == 1 else 1.8),
            fillcolor=f'rgba({r},{g},{b},0.08)',
            marker=dict(size=5 if len(sub) <= 4 else 3),
            hovertemplate='<br>'.join(hover_lines) + '<extra>' + row['Nombre'] + '</extra>',
        ))


     # ── Trazas especiales (mejor, promedio, peor) ──
    highlight_colors = {'best': TEAL, 'avg': COOL, 'worst': HOT}
    highlight_dash   = {'best': 'solid', 'avg': 'dash', 'worst': 'dot'}

    for kind, row in (highlight_traces or []):
        col  = highlight_colors[kind]
        dash = highlight_dash[kind]
        hex_ = col.lstrip('#')
        r, g, b = int(hex_[:2], 16), int(hex_[2:4], 16), int(hex_[4:], 16)
        z_cols      = ['Vel_Z', 'Ag_Z', 'Star_Z']
        r_vals      = [(row.get(zc, 0) + offset) for zc in z_cols]
        hover_lines = [f"<b>{lbl}</b>: z={row.get(zc, 0):+.3f}"
                       for lbl, zc in zip(labels, z_cols)]
        fig.add_trace(go.Scatterpolar(
            r=r_vals, theta=labels, fill='toself', name=row['Nombre'],
            line=dict(color=col, width=2.8, dash=dash),
            fillcolor=f'rgba({r},{g},{b},0.08)',
            marker=dict(size=6),
            hovertemplate='<br>'.join(hover_lines) + '<extra>' + row['Nombre'] + '</extra>',
        ))

    fig.update_layout(
        **PLOT_BASE, height=340,
        polar=dict(
            bgcolor=SURF2,
            radialaxis=dict(
                visible=True, range=[0, axis_max],
                tickvals=tick_vals,
                ticktext=tick_text,
                gridcolor=FAINT,
                tickfont=dict(size=9, color=MUTED),
                tickcolor='rgba(0,0,0,0)',
            ),
            angularaxis=dict(gridcolor=FAINT, tickfont=dict(size=12, color=MUTED)),
        ),
        showlegend=True,
        legend=dict(font=dict(size=10, color=MUTED), bgcolor='rgba(0,0,0,0)',
                    x=1.05, y=0.1),
    )
    return fig


def fig_bar(sub):
    colors = [nc(n) for n in sub['Nivel']]
    max_abs = max(sub['Overall_Z'].abs().max(), 1.0) if len(sub) else 1.0
    axis_lim = max_abs * 1.25

    fig = go.Figure(go.Bar(
        x=sub['Overall_Z'], y=sub['Nombre'],
        orientation='h',
        marker=dict(
            color=[hex_to_rgba(c) for c in colors],
            line=dict(color=colors, width=1),
        ),
        text=sub['Overall_Z'].round(2),
        textposition='outside',
        textfont=dict(color=MUTED, size=10),

        customdata=list(zip(sub['Nivel'], sub['Vel_Z'],
                            sub['Ag_Z'], sub['Star_Z'])),
        hovertemplate=(
            '<b>%{y}</b><br>Z promedio: %{x:.2f} · Nivel: %{customdata[0]}<br>'
            'Vel Z: %{customdata[1]:.3f} | 5-10-5 Z: %{customdata[2]:.3f} | '
            'Star Z: %{customdata[3]:.3f}<extra></extra>'
        )
    ))
    fig.update_layout(
        **PLOT_BASE,
        height=max(220, len(sub) * 34 + 60),
        xaxis=dict(range=[-axis_lim, axis_lim], gridcolor=FAINT,
                   tickfont=dict(color=MUTED), zeroline=True, zerolinecolor=FAINT,
                   showline=False),
        yaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(color=MUTED, size=11),
                   categoryorder='array',
                   categoryarray=sub['Nombre'].tolist()),
        bargap=0.35,
    )
    return fig


def detail_card(row):
    nivel_col = nc(row['Nivel'])
    badge_col = {'Alto': 'success', 'Medio': 'warning', 'Bajo': 'danger'}[row['Nivel']]

    def mblock(label, zscore, norm, accent):
        return dbc.Col(html.Div([
            html.Div(style={'height': '2px', 'background': accent,
                            'borderRadius': '2px 2px 0 0', 'marginBottom': '10px'}),
            html.Div(label, style={'fontSize': '10px', 'color': MUTED,
                                   'textTransform': 'uppercase', 'letterSpacing': '.6px',
                                   'marginBottom': '6px'}),
            html.Div([
                html.Span(f'{zscore:+.3f}',
                          style={'fontFamily': 'Space Grotesk,sans-serif',
                                 'fontSize': '20px', 'fontWeight': '700'}),
                html.Span(' z', style={'fontSize': '11px', 'color': MUTED, 'marginLeft': '2px'}),
            ]),
            html.Div(f'Percentil aprox: {norm:.0f}/100',
                     style={'fontSize': '10px', 'color': MUTED, 'marginTop': '3px'}),
        ], style={'background': SURF2, 'borderRadius': '8px', 'padding': '12px 14px'}),
        md=4, style={'marginBottom': '8px'})

    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div(row['Nombre'][-3:], style={
                        'width': '46px', 'height': '46px', 'borderRadius': '50%',
                        'background': f'linear-gradient(135deg,{COOL},{TEAL})',
                        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                        'fontWeight': '700', 'fontSize': '14px', 'color': '#fff',
                        'marginRight': '14px', 'flexShrink': '0',
                    }),
                    html.Div([
                        html.Div(row['Nombre'],
                                 style={'fontFamily': 'Space Grotesk,sans-serif',
                                        'fontSize': '19px', 'fontWeight': '700'}),
                        dbc.Badge(row['Nivel'], color=badge_col,
                                  style={'fontSize': '10px', 'marginTop': '4px'}),
                    ])
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ], md=8),
            dbc.Col([
                html.Div(f'{row["Overall"]:.1f}',
                         style={'fontFamily': 'Space Grotesk,sans-serif',
                                'fontSize': '38px', 'fontWeight': '700',
                                'color': nivel_col, 'textAlign': 'right', 'lineHeight': '1'}),
                html.Div('Score global',
                         style={'fontSize': '10px', 'color': MUTED,
                                'textTransform': 'uppercase', 'letterSpacing': '.6px',
                                'textAlign': 'right'}),
            ], md=4),
        ], className='mb-3 align-items-center'),
        dbc.Row([
            mblock('Velocidad',  row['Velocidad'], row['Vel_N'],  HOT),
            mblock('5 - 10 - 5', row['5_10_5'],   row['Ag_N'],   COOL),
            mblock('Star Drill', row['StarDrill'], row['Star_N'], TEAL),
        ]),
    ])


# ══════════════════════════════════════════
# JUMP METRICS CONFIG  (métricas exactas solicitadas)
# ══════════════════════════════════════════
JUMP_CFG = {
    'cmj': {
        'title': 'CMJ — Countermovement Jump',
        'color': HOT,
        'metrics': [
            # (etiqueta, col_raw, col_z, color, unidad)
            ('Altura de salto',      'cmj_altura_raw',     'cmj_altura_z',     TEAL, 'cm'),
            ('Tiempo de vuelo',      'cmj_vuelo_raw',      'cmj_vuelo_z',      COOL, 'ms'),
            ('Fuerza de impulso',    'cmj_potencia_raw',   'cmj_potencia_z',   GOLD, 'W'),
            ('Fuerza de aterrizaje', 'cmj_aterrizaje_raw', 'cmj_aterrizaje_z', HOT,  'N'),
            ('RSI',                  'cmj_rsi_raw',        'cmj_rsi_z',        '#8B5CF6', ''),
        ]
    },
    'sj': {
        'title': 'SJ — Squat Jump',
        'color': COOL,
        'metrics': [
            ('Altura de salto',      'sj_altura_raw',     'sj_altura_z',     TEAL, 'cm'),
            ('Tiempo de vuelo',      'sj_vuelo_raw',      'sj_vuelo_z',      COOL, 'ms'),
            ('Fuerza de impulso',    'sj_potencia_raw',   'sj_potencia_z',   GOLD, 'W'),
            ('Fuerza de aterrizaje', 'sj_aterrizaje_raw', 'sj_aterrizaje_z', HOT,  'N'),
        ]
    },
    'dj': {
        'title': 'DJ',
        'color': TEAL,
        'metrics': [
            ('Altura de salto',      'dj_altura_raw',     'dj_altura_z',     TEAL, 'cm'),
            ('Tiempo de vuelo',      'dj_vuelo_raw',      'dj_vuelo_z',      COOL, 'ms'),
            ('Fuerza de impulso',    'dj_potencia_raw',   'dj_potencia_z',   GOLD, 'W'),
            ('Fuerza de aterrizaje', 'dj_aterrizaje_raw', 'dj_aterrizaje_z', HOT,  'N'),
            ('RSI',                  'dj_rsi_raw',        'dj_rsi_z',        '#8B5CF6', ''),
        ]
    },
}

# ── Normalizar métricas de salto a 0-100 para el radar ──
def normalize_jump_metrics(jump_type, player_ids):
    """Devuelve df con columnas _N (0-100) para cada métrica del tipo de salto."""
    cfg  = JUMP_CFG[jump_type]
    cols = [col for _, col, _, _ in cfg['metrics']]
    sub  = df[df['Nombre'].isin(player_ids)][['Nombre'] + cols].copy()

    # Para métricas donde MENOS es mejor (fuerzas de aterrizaje, tiempo), invertir
    invert = {'cmj_aterrizaje', 'sj_aterrizaje', 'dj_aterrizaje', 'dj_tiempo', 'dj_impacto'}

    for col in cols:
        s   = pd.to_numeric(sub[col], errors='coerce')
        mn, mx = s.min(), s.max()
        if pd.isna(mn) or mx == mn:
            sub[col + '_N'] = 50.0
        else:
            norm = (s - mn) / (mx - mn) * 100
            sub[col + '_N'] = (100 - norm) if col in invert else norm
        sub[col + '_N'] = sub[col + '_N'].round(1)
    return sub


def fig_jump_radar(jump_type, player_ids):
    cfg    = JUMP_CFG[jump_type]
    labels   = [lbl     for lbl, _, _, _, _    in cfg['metrics']]
    cols_raw = [col_raw for _, col_raw, _, _, _ in cfg['metrics']]
    cols_z   = [col_z   for _, _, col_z, _, _   in cfg['metrics']]
    units    = [u       for _, _, _, _, u        in cfg['metrics']]

    sub = df[df['Nombre'].isin(player_ids)].copy()
    if sub.empty:
        return None

    # ── CMJ: z-score directo (ya vienen del Excel estandarizados) ──
    if jump_type == 'cmj':
        # Invertir fuerza de aterrizaje: menor fuerza = mejor rendimiento
        INVERT_CMJ = {'cmj_aterrizaje'}

        # Rango del eje: z típico -3 a +3, desplazado para que empiece en 0
        offset   = 3.5
        axis_max = 7.0
        tick_vals  = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
        tick_text  = ['z=-3', 'z=-2', 'z=-1', 'z=0', 'z=+1', 'z=+2', 'z=+3']

        fig = go.Figure()
        for i, (_, row) in enumerate(sub.iterrows()):
            color = RADAR_COLORS[i % len(RADAR_COLORS)]
            hex_  = color.lstrip('#')
            r, g, b = int(hex_[:2], 16), int(hex_[2:4], 16), int(hex_[4:], 16)

            r_vals      = []
            hover_lines = []
            for col_raw, col_z, lbl, unit in zip(cols_raw, cols_z, labels, units):
                z = pd.to_numeric(row.get(col_z, np.nan), errors='coerce')
                if col_z in INVERT_CMJ:
                    z = -z  # invertir: menos fuerza de aterrizaje = mejor
                r_vals.append((z + offset) if pd.notna(z) else offset)

                inv_note = ' ↓mejor' if col_z in INVERT_CMJ else ''
                if pd.notna(row.get(col_z, np.nan)):
                    hover_lines.append(
                        f"<b>{lbl}</b>{inv_note}: z={row.get(col_z, np.nan):+.3f}"
                    )
                else:
                    hover_lines.append(f"<b>{lbl}</b>: sin datos")

            fig.add_trace(go.Scatterpolar(
                r=r_vals,
                theta=labels,
                fill='toself',
                name=row['Nombre'],
                line=dict(color=color, width=2.5 if len(sub) == 1 else 1.8),
                fillcolor=f'rgba({r},{g},{b},0.12)',
                marker=dict(size=6 if len(sub) <= 4 else 4),
                hovertemplate='<br>'.join(hover_lines) + '<extra>' + row['Nombre'] + '</extra>',
            ))

        fig.update_layout(
            **PLOT_BASE, height=440,
            polar=dict(
                bgcolor=SURF2,
                radialaxis=dict(
                    visible=True,
                    range=[0, axis_max],
                    tickvals=tick_vals,
                    ticktext=tick_text,
                    gridcolor=FAINT,
                    tickfont=dict(size=9, color=MUTED),
                    tickcolor='rgba(0,0,0,0)',
                ),
                angularaxis=dict(gridcolor=FAINT, tickfont=dict(size=11, color=TEXT), rotation=90),
            ),
            showlegend=True,
            legend=dict(font=dict(size=11, color=MUTED), bgcolor='rgba(0,0,0,0)',
                        orientation='h', y=-0.12, x=0.5, xanchor='center'),
            transition=dict(duration=400, easing='cubic-in-out'),
        )
        return fig

    # ── SJ / DJ: normalización min-max 0-100 como antes ──
    invert_minmax = {'sj_aterrizaje', 'dj_aterrizaje', 'dj_tiempo', 'dj_impacto'}
    offset   = 3.5
    axis_max = 7.0
    tick_vals = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
    tick_text = ['z=-3', 'z=-2', 'z=-1', 'z=0', 'z=+1', 'z=+2', 'z=+3']

    fig = go.Figure()
    for i, (_, row) in enumerate(sub.iterrows()):
        color = RADAR_COLORS[i % len(RADAR_COLORS)]
        hex_  = color.lstrip('#')
        r, g, b = int(hex_[:2], 16), int(hex_[2:4], 16), int(hex_[4:], 16)

        r_vals      = []
        hover_lines = []
        for col_raw, col_z, lbl, unit in zip(cols_raw, cols_z, labels, units):
            z   = pd.to_numeric(row.get(col_z, np.nan), errors='coerce')
            raw = pd.to_numeric(row.get(col_raw, np.nan), errors='coerce')
            r_vals.append((z + offset) if pd.notna(z) else offset)
            if pd.notna(raw):
                hover_lines.append(f"<b>{lbl}</b>: {raw:.2f} {unit} (z={z:+.2f})")
            else:
                hover_lines.append(f"<b>{lbl}</b>: sin datos")

        fig.add_trace(go.Scatterpolar(
            r=r_vals, theta=labels, fill='toself', name=row['Nombre'],
            line=dict(color=color, width=2.5 if len(sub) == 1 else 1.8),
            fillcolor=f'rgba({r},{g},{b},0.12)',
            marker=dict(size=6 if len(sub) <= 4 else 4),
            hovertemplate='<br>'.join(hover_lines) + '<extra>' + row['Nombre'] + '</extra>',
        ))

    fig.update_layout(
        **PLOT_BASE, height=440,
        polar=dict(
            bgcolor=SURF2,
            radialaxis=dict(
                visible=True, range=[0, axis_max],
                tickvals=tick_vals,
                ticktext=tick_text,
                gridcolor=FAINT,
                tickfont=dict(size=9, color=MUTED),
                tickcolor='rgba(0,0,0,0)',
            ),
            angularaxis=dict(gridcolor=FAINT, tickfont=dict(size=11, color=TEXT), rotation=90),
        ),
        showlegend=True,
        legend=dict(font=dict(size=11, color=MUTED), bgcolor='rgba(0,0,0,0)',
                    orientation='h', y=-0.12, x=0.5, xanchor='center'),
        transition=dict(duration=400, easing='cubic-in-out'),
    )
    return fig

def fig_jump_bar(jump_type, player_ids):
    """Barras agrupadas con valores reales (sin normalizar) por jugador."""
    cfg    = JUMP_CFG[jump_type]
    labels   = [lbl   for lbl, _, _, _, _  in cfg['metrics']]
    cols_raw = [cr    for _, cr, _, _, _    in cfg['metrics']]
    cols_z   = [cz    for _, _, cz, _, _    in cfg['metrics']]
    units    = [u     for _, _, _, _, u     in cfg['metrics']]

    sub = df[df['Nombre'].isin(player_ids)].copy()
    if sub.empty:
        return None

    # Verificar que al menos una métrica tiene datos
    has_data = any(col in sub.columns and sub[col].notna().any() for col in cols_z)
    if not has_data:
        return None

    fig = go.Figure()
    for i, (_, row) in enumerate(sub.iterrows()):
        color = RADAR_COLORS[i % len(RADAR_COLORS)]
        y_vals, x_lbls, hover_text = [], [], []
        for lbl, col_raw, col_z, unit in zip(labels, cols_raw, cols_z, units):
            v_raw = row.get(col_raw, np.nan)
            v_z   = row.get(col_z, np.nan)
            if pd.notna(v_z):
                y_vals.append(round(float(v_z), 3))
                x_lbls.append(lbl)
                hover_text.append(
                    f'{lbl}: {v_raw:.2f} {unit} (z={v_z:+.2f})' if pd.notna(v_raw)
                    else f'{lbl}: z={v_z:+.2f}'
                )
        if y_vals:
            fig.add_trace(go.Bar(
                name=row['Nombre'],
                x=x_lbls,
                y=y_vals,
                marker_color=hex_to_rgba(color, 0.75),
                marker_line=dict(color=color, width=1.5),
                hovertemplate='<b>' + row['Nombre'] + '</b><br>%{x}: %{y:.3f}<extra></extra>',
            ))

    fig.update_layout(
        **PLOT_BASE, height=340, barmode='group',
        xaxis=dict(gridcolor=FAINT, tickfont=dict(color=MUTED, size=11), zeroline=False),
        yaxis=dict(gridcolor=FAINT, tickfont=dict(color=MUTED, size=10),
                   zeroline=True, zerolinecolor=FAINT),
        legend=dict(font=dict(size=10, color=MUTED), bgcolor='rgba(0,0,0,0)',
                    orientation='h', y=-0.18, x=0.5, xanchor='center'),
        bargap=0.2, bargroupgap=0.06,
        transition=dict(duration=350, easing='cubic-in-out'),
    )
    return fig


def jump_metric_cards(jump_type, player_ids):
    """Tarjetas de resumen con valor promedio de cada métrica."""
    cfg = JUMP_CFG[jump_type]
    sub = df[df['Nombre'].isin(player_ids)]
    cards = []
    for label, col_raw, col_z, color, unit in cfg['metrics']:
        vals = sub[col_raw].dropna() if col_raw in sub.columns else pd.Series(dtype=float)
        if len(vals) > 0:
            val_display = f'{vals.mean():.2f}'
            sub_lbl = f'Promedio · n={len(vals)}'
            mn, mx = df[col_raw].min(), df[col_raw].max()
            pct = ((vals.mean() - mn) / (mx - mn) * 100) if mx != mn else 50
            pct = round(pct, 1)
        else:
            val_display = '—'
            sub_lbl = 'Sin datos'
            pct = 0

        cards.append(dbc.Col(
            html.Div([
                html.Div(style={'height': '2px', 'background': color,
                                'borderRadius': '2px 2px 0 0', 'marginBottom': '10px'}),
                html.Div(label, style={'fontSize': '11px', 'color': MUTED,
                                       'lineHeight': '1.4', 'marginBottom': '8px'}),
                html.Div([
                    html.Span(val_display,
                              style={'fontFamily': 'Space Grotesk,sans-serif',
                                     'fontSize': '22px', 'fontWeight': '700', 'color': TEXT}),
                    html.Span(f' {unit}' if unit else '',
                              style={'fontSize': '11px', 'color': MUTED}),
                ]),
                html.Div(sub_lbl, style={'fontSize': '10px', 'color': FAINT, 'marginTop': '5px'}),
            ], style={
                'background': SURF,
                'border': f'1px solid {FAINT}',
                'borderRadius': '8px',
                'padding': '13px 14px',
                'height': '100%',
                'transition': 'all .3s ease',
            }),
            xs=6, md=4, lg=3, style={'marginBottom': '10px'}
        ))
    return dbc.Row(cards)


# ══════════════════════════════════════════
# APP LAYOUT
# ══════════════════════════════════════════
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700'
        '&family=Space+Grotesk:wght@400;500;700&display=swap',
    ],
    suppress_callback_exceptions=True,
)
app.title = 'UAO Fútbol Sala'

# ── CSS de animaciones ──
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            @keyframes pulse {
                0%   { opacity: 1; transform: scale(1);   }
                50%  { opacity: .5; transform: scale(1.3); }
                100% { opacity: 1; transform: scale(1);   }
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to   { opacity: 1; transform: translateY(0);   }
            }
            .fade-in { animation: fadeIn .35s ease forwards; }
            ::-webkit-scrollbar { width: 6px; }
            ::-webkit-scrollbar-track { background: #0d0f14; }
            ::-webkit-scrollbar-thumb { background: #3D4560; border-radius: 3px; }
            .js-plotly-plot .plotly .modebar { display: none !important; }
            .jump-dropdown .Select-control { background: #1c2030 !important; border-color: #3D4560 !important; }
            .jump-dropdown .Select-menu-outer { background: #1c2030 !important; border-color: #3D4560 !important; }
            .jump-dropdown .Select-option { color: #F0F2F8 !important; background: #1c2030 !important; }
            .jump-dropdown .Select-option:hover, .jump-dropdown .VirtualizedSelectFocusedOption { background: #232840 !important; }
            .jump-dropdown .Select-value-label, .jump-dropdown .Select-placeholder { color: #8892A4 !important; }
            .Select-multi-value-wrapper .Select-value { background: #232840 !important; border-color: #3D4560 !important; color: #F0F2F8 !important; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

card_style   = {'background': SURF, 'border': f'1px solid {FAINT}', 'borderRadius': '12px'}
header_style = {'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                'padding': '13px 18px 11px', 'borderBottom': f'1px solid {FAINT}'}


def card(title, hint, children, extra_style=None):
    s = {**card_style, **(extra_style or {})}
    return html.Div([
        html.Div([
            html.Span(title, style={'fontSize': '11px', 'color': MUTED,
                                    'textTransform': 'uppercase', 'letterSpacing': '.8px',
                                    'fontWeight': '600'}),
            html.Span(hint, style={'fontSize': '11px', 'color': FAINT}),
        ], style=header_style),
        html.Div(children, style={'padding': '14px 16px'}),
    ], style=s)


def sidebar_link_style(active):
    base = {
        'display': 'flex', 'alignItems': 'center', 'gap': '10px',
        'padding': '10px 14px', 'borderRadius': '8px', 'fontSize': '13px',
        'fontWeight': '500', 'cursor': 'pointer', 'fontFamily': 'Inter,sans-serif',
        'marginBottom': '4px', 'transition': 'all .2s', 'border': 'none',
        'width': '100%', 'textAlign': 'left',
    }
    if active:
        base.update({'background': TEAL + '1e', 'color': TEAL, 'fontWeight': '600'})
    else:
        base.update({'background': 'transparent', 'color': MUTED})
    return base


app.layout = html.Div([

    # ── HEADER ──
    html.Div([
        html.Div([
            html.Div('⚽', style={'fontSize': '22px', 'marginRight': '12px'}),
            html.Div([
                html.Div('UAO Fútbol Sala',
                         style={'fontFamily': 'Space Grotesk,sans-serif',
                                'fontSize': '17px', 'fontWeight': '700', 'color': TEXT}),
                html.Div('Análisis de rendimiento',
                         style={'fontSize': '10px', 'color': MUTED,
                                'textTransform': 'uppercase', 'letterSpacing': '.5px'}),
            ]),
        ], style={'display': 'flex', 'alignItems': 'center'}),

        html.Div([
            html.Button([html.Span('⭱', style={'marginRight': '8px'}), 'Importar datos'],
                        id='btn-import',
                        style={'padding': '9px 16px', 'borderRadius': '8px', 'fontSize': '13px',
                               'fontWeight': '500', 'cursor': 'pointer',
                               'border': f'1px solid {FAINT}',
                               'background': 'transparent', 'color': TEXT,
                               'fontFamily': 'Inter,sans-serif'}),
        ], style={'display': 'flex', 'alignItems': 'center'}),

    ], style={'background': SURF, 'borderBottom': f'1px solid {FAINT}',
              'padding': '14px 28px', 'position': 'sticky', 'top': '0', 'zIndex': '100',
              'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}),

    # ── BODY (sidebar + contenido) ──
    html.Div([

        # ── SIDEBAR ──
        html.Div([
            html.Button(
                [html.Span('🏃', style={'marginRight': '10px'}), 'Rendimiento físico'],
                id='tab-btn-rend', n_clicks=0, style=sidebar_link_style(True),
            ),
            html.Button(
                [html.Span('⤒', style={'marginRight': '10px'}), 'Análisis de saltos'],
                id='tab-btn-salt', n_clicks=0, style=sidebar_link_style(False),
            ),
        ], style={'width': '210px', 'flexShrink': '0', 'background': SURF,
                  'border': f'1px solid {TEXT}', 'borderRadius': '12px',
                  'padding': '14px', 'alignSelf': 'flex-start',
                  'position': 'sticky', 'top': '92px'}),

        # ── CONTENIDO ──
        html.Div([

        # ═══ SECCIÓN RENDIMIENTO ═══
        html.Div(id='sec-rend', children=[

            html.Div([
                html.Span('Deportistas', style={'fontSize': '11px', 'color': MUTED,
                                                'textTransform': 'uppercase', 'letterSpacing': '.8px',
                                                'fontWeight': '600', 'marginRight': '14px',
                                                'whiteSpace': 'nowrap'}),
                dcc.Dropdown(
                    id='rend-player-select',
                    options=[{'label': pid, 'value': pid}
                             for pid in sorted(ALL_IDS, key=lambda x: int(x.split('_')[1]))],
                    value=[],
                    multi=True,
                    placeholder='Seleccionar deportistas...',
                    style={'flex': '1', 'fontSize': '12px', 'fontFamily': 'Inter,sans-serif'},
                    className='jump-dropdown',
                ),
                html.Div([
                    dcc.Checklist(
                        id='rend-highlights',
                        options=[
                            {'label': ' Alto rendimiento', 'value': 'best'},
                            {'label': ' Rendimiento promedio', 'value': 'avg'},
                            {'label': ' Bajo rendimiento',  'value': 'worst'},
                        ],
                        value=[],
                        inline=True,
                        style={'fontSize': '12px', 'color': MUTED,
                               'fontFamily': 'Inter,sans-serif'},
                        inputStyle={'marginRight': '4px', 'accentColor': TEAL},
                        labelStyle={'marginRight': '14px', 'cursor': 'pointer'},
                    ),
                ], style={'marginLeft': '16px', 'whiteSpace': 'nowrap'}),
            ], style={'background': SURF, 'border': f'1px solid {FAINT}', 'borderRadius': '12px',
                      'padding': '13px 18px', 'marginBottom': '14px',
                      'display': 'flex', 'alignItems': 'center'}),


            dbc.Row(id='stats-row', className='g-2 mb-3'),

            dbc.Row([
                dbc.Col(card('Perfil por métricas', 'Radar comparativo',
                             dcc.Graph(id='chart-radar', config={'displayModeBar': False})),
                        md=6, style={'marginBottom': '14px'}),
                dbc.Col([
                    card('Comparación directa', 'Clic en barra → ver detalle', [
                        html.Div([
                            *[html.Span([
                                html.Span(style={'display': 'inline-block', 'width': '7px',
                                                 'height': '7px', 'borderRadius': '50%',
                                                 'background': c, 'marginRight': '5px'}),
                                lbl,
                            ], style={'fontSize': '11px', 'color': MUTED, 'marginRight': '14px'})
                              for lbl, c in [('Alto', TEAL), ('Medio', GOLD), ('Bajo', HOT)]],
                        ], style={'marginBottom': '8px'}),
                        dcc.Graph(id='chart-bar', config={'displayModeBar': False}),
                    ]),
                ], md=6, style={'marginBottom': '14px'}),
            ]),

            html.Div([
                html.Div([
                    html.Span('ⓘ ', style={'color': COOL, 'fontSize': '13px'}),
                    html.Span('¿Cómo interpretar?',
                              style={'fontSize': '11px', 'color': MUTED,
                                     'textTransform': 'uppercase', 'letterSpacing': '.8px',
                                     'fontWeight': '600'}),
                ], style={**header_style, 'border': 'none', 'padding': '13px 18px 10px'}),
                html.Div([
                    html.P('Los valores están expresados en Z-score.',
                           style={'fontSize': '12.5px', 'color': TEXT, 'marginBottom': '12px',
                                  'lineHeight': '1.5'}),
                    html.Div([
                        html.Span('0', style={'color': MUTED, 'fontWeight': '700',
                                               'marginRight': '8px'}),
                        html.Span('= Promedio del grupo',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '8px'}),
                    html.Div([
                        html.Span('+1', style={'color': TEAL, 'fontWeight': '700',
                                                'marginRight': '8px'}),
                        html.Span('= Desviación estándar por encima del promedio',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '8px'}),
                    html.Div([
                        html.Span('-1', style={'color': HOT, 'fontWeight': '700',
                                                'marginRight': '8px'}),
                        html.Span('= Desviación estándar por debajo del promedio',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '14px'}),
                    html.Div(style={'height': '1px', 'background': TEXT,
                                    'marginBottom': '12px'}),
                    html.P('Valores positivos indican mejor rendimiento relativo al equipo.',
                           style={'fontSize': '12px', 'color': MUTED, 'lineHeight': '1.5',
                                  'marginBottom': '0'}),
                ], style={'padding': '0 18px 18px'}),
            ], style={**card_style, 'marginBottom': '14px'}),
        ]),

        # ═══ SECCIÓN SALTOS ═══
        html.Div(id='sec-salt', style={'display': 'none'}, children=[

            # ── Fila superior: sub-tabs + selector de jugador ──
            html.Div([
                # Sub-tabs CMJ / SJ / DJ
                html.Div([
                    html.Button('CMJ', id='jt-cmj', n_clicks=0,
                                style={'padding': '8px 22px', 'borderRadius': '6px',
                                       'fontSize': '13px', 'fontWeight': '600',
                                       'cursor': 'pointer', 'border': 'none',
                                       'background': HOT, 'color': '#fff',
                                       'fontFamily': 'Inter,sans-serif',
                                       'marginRight': '4px', 'transition': 'all .25s'}),
                    html.Button('SJ', id='jt-sj', n_clicks=0,
                                style={'padding': '8px 22px', 'borderRadius': '6px',
                                       'fontSize': '13px', 'fontWeight': '500',
                                       'cursor': 'pointer', 'border': 'none',
                                       'background': 'transparent', 'color': MUTED,
                                       'fontFamily': 'Inter,sans-serif',
                                       'marginRight': '4px', 'transition': 'all .25s'}),
                    html.Button('DJ', id='jt-dj', n_clicks=0,
                                style={'padding': '8px 22px', 'borderRadius': '6px',
                                       'fontSize': '13px', 'fontWeight': '500',
                                       'cursor': 'pointer', 'border': 'none',
                                       'background': 'transparent', 'color': MUTED,
                                       'fontFamily': 'Inter,sans-serif',
                                       'transition': 'all .25s'}),
                ], style={'background': SURF2, 'borderRadius': '8px', 'padding': '4px',
                          'display': 'inline-flex', 'alignItems': 'center'}),

                # Selector de jugadores (multi-select dropdown)
                html.Div([
                    html.Span('Jugadores',
                              style={'fontSize': '11px', 'color': MUTED,
                                     'textTransform': 'uppercase', 'letterSpacing': '.6px',
                                     'fontWeight': '600', 'marginRight': '10px',
                                     'whiteSpace': 'nowrap'}),
                    dcc.Dropdown(
                        id='jump-player-select',
                        options=[{'label': pid, 'value': pid}
                                 for pid in sorted(ALL_IDS, key=lambda x: int(x.split('_')[1]))],
                        value=[],
                        multi=True,
                        placeholder='Seleccionar jugadores...',
                        style={
                            'width': '420px',
                            'fontSize': '12px',
                            'fontFamily': 'Inter,sans-serif',
                        },
                        className='jump-dropdown',
                    ),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginLeft': 'auto'}),

            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
                      'marginBottom': '18px', 'flexWrap': 'wrap', 'gap': '10px'}),

            # ── Tarjetas de métricas ──
            html.Div(id='jump-cards', className='fade-in',
                     style={'marginBottom': '14px'}),

            # ── Radar + Barras lado a lado ──
            dbc.Row([
                dbc.Col(
                    html.Div(id='jump-radar-wrap',
                             style={**card_style, 'padding': '14px 16px'}),
                    md=6, style={'marginBottom': '14px'}
                ),
                dbc.Col(
                    html.Div(id='jump-bar-wrap',
                             style={**card_style, 'padding': '14px 16px'}),
                    md=6, style={'marginBottom': '14px'}
                ),
            ]),

            html.Div([
                html.Div([
                    html.Span('ⓘ ', style={'color': COOL, 'fontSize': '13px'}),
                    html.Span('¿Cómo interpretar?',
                              style={'fontSize': '11px', 'color': MUTED,
                                     'textTransform': 'uppercase', 'letterSpacing': '.8px',
                                     'fontWeight': '600'}),
                ], style={**header_style, 'border': 'none', 'padding': '13px 18px 10px'}),
                html.Div([
                    html.P('Los valores están expresados en Z-score.',
                           style={'fontSize': '12.5px', 'color': TEXT, 'marginBottom': '12px',
                                  'lineHeight': '1.5'}),
                    html.Div([
                        html.Span('0', style={'color': MUTED, 'fontWeight': '700',
                                               'marginRight': '8px'}),
                        html.Span('= Promedio del grupo',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '8px'}),
                    html.Div([
                        html.Span('+1', style={'color': TEAL, 'fontWeight': '700',
                                                'marginRight': '8px'}),
                        html.Span('= Desviación estándar por encima del promedio',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '8px'}),
                    html.Div([
                        html.Span('-1', style={'color': HOT, 'fontWeight': '700',
                                                'marginRight': '8px'}),
                        html.Span('= Desviación estándar por debajo del promedio',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '14px'}),
                    html.Div(style={'height': '1px', 'background': FAINT,
                                    'marginBottom': '12px'}),
                    html.P('Valores positivos indican mejor rendimiento relativo al equipo.',
                           style={'fontSize': '12px', 'color': MUTED, 'lineHeight': '1.5',
                                  'marginBottom': '0'}),
                ], style={'padding': '0 18px 18px'}),
            ], style={**card_style, 'marginBottom': '14px'}),
        ]),

        ], style={'flex': '1', 'minWidth': '0'}),

    ], style={'display': 'flex', 'gap': '20px', 'padding': '22px 28px',
              'maxWidth': '1500px', 'margin': '0 auto'}),

    # ── Stores ──
    dcc.Store(id='st-tab',  data='rend'),
    dcc.Store(id='st-jtab', data='cmj'),

], style={'background': BG, 'minHeight': '100vh', 'color': TEXT,
          'fontFamily': 'Inter,sans-serif'})


# 3 · Charts + stats + crumb + undo/redo
@app.callback(
    Output('chart-radar', 'figure'),
    Output('chart-bar',   'figure'),
    Output('stats-row',   'children'),
    Input('rend-player-select', 'value'),
    Input('rend-highlights',    'value'),
)
def update_charts(sel, highlights):
    sel        = sel or []
    highlights = highlights or []

    sub = df[df['Nombre'].isin(sel)].sort_values('Overall', ascending=False)
    n   = len(sub)

    # Si no hay selección individual ni highlights, mostrar vacío
    if not sel and not highlights:
        empty_fig = go.Figure().update_layout(
            paper_bgcolor=SURF, plot_bgcolor=SURF,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            annotations=[dict(
                text='Selecciona al menos un deportista',
                x=0.5, y=0.5, xref='paper', yref='paper',
                showarrow=False, font=dict(size=13, color=MUTED),
            )]
        )
        empty_stats = [
            dbc.Col(html.Div([
                html.Div('—', style={'fontFamily': 'Space Grotesk,sans-serif',
                                     'fontSize': '24px', 'fontWeight': '700',
                                     'color': TEXT, 'lineHeight': '1', 'marginBottom': '3px'}),
                html.Div(lbl, style={'fontSize': '10px', 'color': MUTED,
                                     'textTransform': 'uppercase', 'letterSpacing': '.6px'}),
            ], style={'background': SURF, 'border': f'1px solid {FAINT}',
                      'borderRadius': '10px', 'padding': '14px 16px'}),
            xs=6, md=3, className='g-2')
            for lbl in ['Total deportistas', 'Nivel alto', 'Nivel medio', 'Nivel bajo']
        ]
        return empty_fig, empty_fig, empty_stats

    def stat_card(val, lbl, color, icon):
        return dbc.Col(html.Div([
            html.Div(icon, style={
                'width': '30px', 'height': '30px', 'borderRadius': '8px',
                'background': color + '1e', 'color': color,
                'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                'fontSize': '14px', 'marginBottom': '10px',
            }),
            html.Div(str(val),
                     style={'fontFamily': 'Space Grotesk,sans-serif', 'fontSize': '24px',
                            'fontWeight': '700', 'color': TEXT, 'lineHeight': '1',
                            'marginBottom': '3px'}),
            html.Div(lbl, style={'fontSize': '10px', 'color': MUTED,
                                 'textTransform': 'uppercase', 'letterSpacing': '.6px'}),
        ], style={'background': SURF, 'border': f'1px solid {FAINT}',
                  'borderRadius': '10px', 'padding': '14px 16px'}),
        xs=6, md=3, className='g-2')

    counts = sub['Nivel'].value_counts()
    stats  = [
        stat_card(n,                       'Total deportistas', COOL, '👥'),
        stat_card(counts.get('Alto',  0),  'Nivel alto',        TEAL, '↗'),
        stat_card(counts.get('Medio', 0),  'Nivel medio',       GOLD, '='),
        stat_card(counts.get('Bajo',  0),  'Nivel bajo',        HOT,  '↓'),
    ]

    highlight_traces = build_highlight_traces(df, highlights)
    return (fig_radar(sub, highlight_traces), fig_bar(sub), stats)


# 6 · Tabs principales
@app.callback(
    Output('sec-rend',     'style'),
    Output('sec-salt',     'style'),
    Output('tab-btn-rend', 'style'),
    Output('tab-btn-salt', 'style'),
    Output('st-tab',       'data'),
    Input('tab-btn-rend',  'n_clicks'),
    Input('tab-btn-salt',  'n_clicks'),
    State('st-tab', 'data'),
    prevent_initial_call=True,
)
def main_tabs(r, s, cur):
    ctx = callback_context
    tid = ctx.triggered[0]['prop_id']
    tab = 'rend' if 'rend' in tid else 'salt'

    if tab == 'rend':
        return (
            {'display': 'block'}, {'display': 'none'},
            sidebar_link_style(True), sidebar_link_style(False), 'rend'
        )
    return (
        {'display': 'none'}, {'display': 'block'},
        sidebar_link_style(False), sidebar_link_style(True), 'salt'
    )


# 7 · Sub-tabs saltos + selector de jugadores → radar + barras + tarjetas
@app.callback(
    Output('jt-cmj',         'style'),
    Output('jt-sj',          'style'),
    Output('jt-dj',          'style'),
    Output('st-jtab',        'data'),
    Output('jump-cards',     'children'),
    Output('jump-radar-wrap','children'),
    Output('jump-bar-wrap',  'children'),

    Input('jt-cmj',              'n_clicks'),
    Input('jt-sj',               'n_clicks'),
    Input('jt-dj',               'n_clicks'),
    Input('jump-player-select',  'value'),
    Input('st-tab',              'data'),

    State('st-jtab', 'data'),
)
def jump_section(c_cmj, c_sj, c_dj, player_sel, main_tab, cur_tab):

    if main_tab != 'salt':
        return (
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update
        )
    ctx = callback_context
    tid = ctx.triggered[0]['prop_id']

    # tab ya fue determinado arriba

    sel = player_sel or []

    # Determinar tab activo aunque no haya selección
    if 'jt-cmj' in tid:
        tab = 'cmj'
    elif 'jt-sj' in tid:
        tab = 'sj'
    elif 'jt-dj' in tid:
        tab = 'dj'
    else:
        tab = cur_tab

    if not sel:
        empty_fig = go.Figure().update_layout(
            paper_bgcolor=SURF, plot_bgcolor=SURF,
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            annotations=[dict(
                text='Selecciona al menos un deportista',
                x=0.5, y=0.5, xref='paper', yref='paper',
                showarrow=False, font=dict(size=13, color=MUTED),
            )]
        )
        tab_colors = {'cmj': HOT, 'sj': COOL, 'dj': TEAL}
        def jbtn_empty(t):
            on = (t == tab)
            return {'padding': '8px 22px', 'borderRadius': '6px', 'fontSize': '13px',
                    'fontWeight': '600' if on else '500',
                    'cursor': 'pointer', 'border': 'none',
                    'fontFamily': 'Inter,sans-serif', 'transition': 'all .25s',
                    'background': tab_colors[t] if on else 'transparent',
                    'color': '#fff' if on else MUTED,
                    'boxShadow': f'0 0 12px {tab_colors[t]}55' if on else 'none'}
        return (
            jbtn_empty('cmj'), jbtn_empty('sj'), jbtn_empty('dj'), tab,
            html.Div(),
            html.Div(dcc.Graph(figure=empty_fig, config={'displayModeBar': False})),
            html.Div(dcc.Graph(figure=empty_fig, config={'displayModeBar': False})),
        )

    # Estilos de botones
    tab_colors = {'cmj': HOT, 'sj': COOL, 'dj': TEAL}
    def jbtn(t):
        on = (t == tab)
        return {'padding': '8px 22px', 'borderRadius': '6px', 'fontSize': '13px',
                'fontWeight': '600' if on else '500',
                'cursor': 'pointer', 'border': 'none',
                'fontFamily': 'Inter,sans-serif', 'transition': 'all .25s',
                'background': tab_colors[t] if on else 'transparent',
                'color': '#fff' if on else MUTED,
                'boxShadow': f'0 0 12px {tab_colors[t]}55' if on else 'none'}

    # Tarjetas
    cards = jump_metric_cards(tab, sel)

    # Radar chart
    jradar = fig_jump_radar(tab, sel)
    radar_content = (
        dcc.Graph(figure=jradar, config={'displayModeBar': False})
        if jradar else
        html.Div([
            html.Div('◎', style={'fontSize': '28px', 'color': FAINT, 'marginBottom': '8px'}),
            html.Div('Sin datos suficientes para el radar',
                     style={'fontSize': '13px', 'color': FAINT}),
        ], style={'display': 'flex', 'flexDirection': 'column',
                  'alignItems': 'center', 'justifyContent': 'center', 'minHeight': '300px'})
    )

    # Bar chart
    jbar = fig_jump_bar(tab, sel)
    bar_content = (
        dcc.Graph(figure=jbar, config={'displayModeBar': False})
        if jbar else
        html.Div([
            html.Div('◎', style={'fontSize': '28px', 'color': FAINT, 'marginBottom': '8px'}),
            html.Div('Sin datos de salto para la selección actual',
                     style={'fontSize': '13px', 'color': FAINT}),
        ], style={'display': 'flex', 'flexDirection': 'column',
                  'alignItems': 'center', 'justifyContent': 'center', 'minHeight': '200px'})
    )

    # Encabezados de las tarjetas de gráficos
    cfg = JUMP_CFG[tab]
    radar_header = html.Div([
        html.Span('● ', style={'color': tab_colors[tab], 'fontSize': '10px'}),
        html.Span('Perfil de salto · ' + ('Z-score' if tab == 'cmj' else 'normalizado 0-100'),
                  style={'fontSize': '11px', 'color': MUTED,
                         'textTransform': 'uppercase', 'letterSpacing': '.7px',
                         'fontWeight': '600'}),
    ], style={'marginBottom': '8px'})

    bar_header = html.Div([
        html.Span('● ', style={'color': tab_colors[tab], 'fontSize': '10px'}),
        html.Span('Valores reales por jugador',
                  style={'fontSize': '11px', 'color': MUTED,
                         'textTransform': 'uppercase', 'letterSpacing': '.7px',
                         'fontWeight': '600'}),
    ], style={'marginBottom': '8px'})

    return (
        jbtn('cmj'), jbtn('sj'), jbtn('dj'), tab,
        cards,
        html.Div([radar_header, radar_content]),
        html.Div([bar_header, bar_content]),
    )


# ══════════════════════════════════════════
# RUN
# ══════════════════════════════════════════
if __name__ == '__main__':
    print('\n🚀  Dashboard en  http://localhost:8050\n')
    if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
