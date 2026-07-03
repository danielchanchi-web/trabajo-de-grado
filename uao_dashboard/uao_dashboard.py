"""
UAO Fútbol Sala — Dashboard de Rendimiento Deportivo
=====================================================
  1. Cambia FILE_PATH con la ruta de tu Excel
  2. Ejecuta:  python uao_dashboard.py
  3. Abre:     http://localhost:8050
"""

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
FILE_PATH = r'C:\Users\danie\Downloads\DATOS_UAO_SOLO_PRUEBAS.xlsx'

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

    # ── Puntuaciones desde "puntuacion" ──
    dp = pd.read_excel(path, sheet_name='puntuacion', header=0)
    dp = dp.iloc[:, [1, 2, 3, 4]].copy()
    dp.columns = ['Nombre', 'Velocidad', '5_10_5', 'StarDrill']
    dp['Nombre'] = dp['Nombre'].astype(str).str.strip()
    for c in ['Velocidad', '5_10_5', 'StarDrill']:
        dp[c] = pd.to_numeric(dp[c], errors='coerce').fillna(0)

    df = dg.merge(dp, on='Nombre', how='left').dropna(subset=['Nombre'])
    df = df[df['Nombre'].str.startswith('UAO_')].reset_index(drop=True)

    def to_100(s):
        mn, mx = s.min(), s.max()
        if mx == mn:
            return pd.Series([50.0] * len(s), index=s.index)
        return ((s - mn) / (mx - mn) * 100).round(1)

    df['Vel_N']   = to_100(df['Velocidad'])
    df['Ag_N']    = to_100(df['5_10_5'])
    df['Star_N']  = to_100(df['StarDrill'])
    df['Overall'] = df[['Vel_N', 'Ag_N', 'Star_N']].mean(axis=1).round(1)
    df['Overall_Z'] = df[['Velocidad', '5_10_5', 'StarDrill']].mean(axis=1).round(3)

    def nivel(s):
        if s >= 66: return 'Alto'
        if s >= 33: return 'Medio'
        return 'Bajo'
    df['Nivel'] = df['Overall'].apply(nivel)

    # ── Saltos desde "Saltos" ──
    ds = pd.read_excel(
    path,
    sheet_name='Saltos',
    header=35
    )

    ds['Nombre'] = ds['Nombre'].astype(str).str.strip()

    def avg_cols(ds_local, pattern):
        if pattern in ds_local.columns:
            return pd.to_numeric(ds_local[pattern], errors='coerce')

        cols = [c for c in ds_local.columns if pattern in str(c)]

        if not cols:
            return pd.Series([np.nan] * len(ds_local), index=ds_local.index)

        return ds_local[cols].apply(
            pd.to_numeric,
            errors='coerce'
        ).mean(axis=1)
    
    # ── Mapeo exacto verificado con el Excel real ──
    jump_cols = {
        # CMJ usando Z-score
        'cmj_rfd_exc':    'braking_RFD_cmj_z',
        'cmj_altura':     'jump_height_cmj_z',
        'cmj_potencia':   'avg_propulsive_power_cmj_z',
        'cmj_aterrizaje': 'peak_landing_force_cmj_z',

        # SJ
        'sj_rfd_conc':    'propulsive_RFD_sj_',
        'sj_altura':      'jump_height_sj_',
        'sj_potencia':    'avg_propulsive_power_sj_',
        'sj_aterrizaje':  'peak_landing_force_sj_',

        # DJ
        'dj_aterrizaje':  'peak_braking_force_dj_',
        'dj_tiempo':      'time_to_peak_braking_force_dj_',
        'dj_rsi':         'RSI__dj_',
        'dj_altura':      'jump_height_dj_',
        'dj_impacto':     'impact_peak_dj_',
    }

    new_cols = {}

    for key, pat in jump_cols.items():
        new_cols[key] = avg_cols(ds, pat)

    ds = pd.concat(
        [ds, pd.DataFrame(new_cols)],
        axis=1

    )

    keep = ['Nombre'] + list(jump_cols.keys())
    ds   = ds[keep].copy()
    df['Nombre'] = df['Nombre'].astype(str).str.strip()
    ds['Nombre'] = ds['Nombre'].astype(str).str.strip()

    df = df.merge(ds, on='Nombre', how='left')
    print(df[['Nombre',
          'cmj_rfd_exc',
          'cmj_altura',
          'cmj_potencia',
          'cmj_aterrizaje']].head())
    df = df.sort_values('Overall', ascending=False).reset_index(drop=True)
    return df


try:
    df = load_data(FILE_PATH)
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
TEXT  = '#1A1D29'
MUTED = '#6B7280'
FAINT = "#717174"
HOT   = '#DC2626'
WARM  = '#EA7E2E'
COOL  = '#2563EB'
TEAL  = '#0D9488'
GOLD  = '#CA8A04'

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

# ══════════════════════════════════════════
# FIGURAS — RENDIMIENTO
# ══════════════════════════════════════════
def fig_radar(sub):
    labels  = ['Velocidad', '5-10-5', 'Star Drill']
    cols    = ['Velocidad', '5_10_5', 'StarDrill']
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
        showlegend=len(sub) <= 8,
        legend=dict(font=dict(size=10, color=MUTED), bgcolor='rgba(0,0,0,0)',
                    x=1.05, y=0.5),
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
        customdata=list(zip(sub['Nivel'], sub['Velocidad'],
                            sub['5_10_5'], sub['StarDrill'])),
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
        # CMJ solo tiene braking_RFD en el Excel → se usa para RFD excéntrica
        # propulsive_RFD no existe en CMJ; se omite RFD concéntrica para no inventar datos
        'metrics': [
            ('RFD excéntrica (frenado)', 'cmj_rfd_exc',    HOT,  'z'),
            ('Altura de salto',          'cmj_altura',     TEAL, 'z'),
            ('Potencia propulsiva',      'cmj_potencia',   GOLD, 'z'),
            ('Fuerza de aterrizaje',     'cmj_aterrizaje', COOL, 'z'),
        ]
    },
    'sj': {
        'title': 'SJ — Squat Jump',
        'color': COOL,
        # SJ solo tiene propulsive_RFD → se usa para RFD concéntrica
        'metrics': [
            ('RFD concéntrica',      'sj_rfd_conc',    HOT,  'N/s'),
            ('Altura de salto',      'sj_altura',      TEAL, 'm'),
            ('Potencia propulsiva',  'sj_potencia',    GOLD, 'W'),
            ('Fuerza de aterrizaje', 'sj_aterrizaje',  COOL, 'N'),
        ]
    },
    'dj': {
        'title': 'DJ',
        'color': TEAL,
        'metrics': [
            ('Fuerza de aterrizaje', 'dj_aterrizaje', HOT,  'N'),
            ('Tiempo de aterrizaje', 'dj_tiempo',     COOL, 'ms'),
            ('RSI',                  'dj_rsi',        GOLD, ''),
            ('Altura de salto',      'dj_altura',     TEAL, 'm'),
            ('Fuerza de impacto',    'dj_impacto',    WARM, 'BW'),
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
    labels = [lbl for lbl, _, _, _ in cfg['metrics']]
    cols   = [col for _, col, _, _ in cfg['metrics']]
    units  = [u   for _, _, _, u   in cfg['metrics']]

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
            for col, lbl, unit in zip(cols, labels, units):
                z = pd.to_numeric(row.get(col, np.nan), errors='coerce')
                if col in INVERT_CMJ:
                    z = -z  # invertir: menos fuerza de aterrizaje = mejor
                r_vals.append((z + offset) if pd.notna(z) else offset)

                inv_note = ' ↓mejor' if col in INVERT_CMJ else ''
                if pd.notna(row.get(col, np.nan)):
                    hover_lines.append(
                        f"<b>{lbl}</b>{inv_note}: z={row.get(col, np.nan):+.3f}"
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
    norm_sub = df[df['Nombre'].isin(player_ids)][['Nombre'] + cols].copy()
    for col in cols:
        s = pd.to_numeric(norm_sub[col], errors='coerce')
        mn, mx = s.min(), s.max()
        if pd.isna(mn) or mx == mn:
            norm_sub[col + '_N'] = 50.0
        else:
            norm = (s - mn) / (mx - mn) * 100
            norm_sub[col + '_N'] = (100 - norm) if col in invert_minmax else norm
        norm_sub[col + '_N'] = norm_sub[col + '_N'].round(1)

    fig = go.Figure()
    for i, (_, row) in enumerate(norm_sub.iterrows()):
        color = RADAR_COLORS[i % len(RADAR_COLORS)]
        hex_  = color.lstrip('#')
        r, g, b = int(hex_[:2], 16), int(hex_[2:4], 16), int(hex_[4:], 16)

        orig_row = sub[sub['Nombre'] == row['Nombre']].iloc[0]
        r_vals      = [row.get(col + '_N', 0) for col in cols]
        hover_lines = []
        for col, lbl, unit in zip(cols, labels, units):
            raw = orig_row.get(col, np.nan)
            inv = ' ↓mejor' if col in invert_minmax else ''
            hover_lines.append(
                f"<b>{lbl}</b>{inv}: {raw:.3f} {unit}" if pd.notna(raw) else f"<b>{lbl}</b>: —"
            )

        fig.add_trace(go.Scatterpolar(
            r=r_vals, theta=labels, fill='toself', name=row['Nombre'],
            line=dict(color=color, width=2.5 if len(norm_sub) == 1 else 1.8),
            fillcolor=f'rgba({r},{g},{b},0.12)',
            marker=dict(size=6 if len(norm_sub) <= 4 else 4),
            hovertemplate='<br>'.join(hover_lines) + '<extra>' + row['Nombre'] + '</extra>',
        ))

    fig.update_layout(
        **PLOT_BASE, height=440,
        polar=dict(
            bgcolor=SURF2,
            radialaxis=dict(
                visible=True, range=[0, 100],
                tickvals=[25, 50, 75, 100],
                gridcolor=FAINT,
                tickfont=dict(size=9, color=MUTED),
                tickcolor='rgba(0,0,0,0)',
            ),
            angularaxis=dict(gridcolor=FAINT, tickfont=dict(size=11, color=TEXT), rotation=90),
        ),
        showlegend=True,
        legend=dict(font=dict(size=11, color=MUTED), bgcolor='rgba(0,0,0,0)',
                    orientation='h', y=-0.12, x=0.5, xanchor='center'),
        annotations=[dict(
            text='Normalizado 0-100 · más área = mejor · ↓mejor = métrica invertida',
            x=0.5, y=1.06, xref='paper', yref='paper',
            showarrow=False, font=dict(size=10, color=FAINT), xanchor='center',
        )],
        transition=dict(duration=400, easing='cubic-in-out'),
    )
    return fig

def fig_jump_bar(jump_type, player_ids):
    """Barras agrupadas con valores reales (sin normalizar) por jugador."""
    cfg    = JUMP_CFG[jump_type]
    labels = [lbl for lbl, _, _, _ in cfg['metrics']]
    cols   = [col for _, col, _, _ in cfg['metrics']]
    units  = [u   for _, _, _, u   in cfg['metrics']]

    sub = df[df['Nombre'].isin(player_ids)].copy()
    if sub.empty:
        return None

    # Verificar que al menos una métrica tiene datos
    has_data = any(col in sub.columns and sub[col].notna().any() for col in cols)
    if not has_data:
        return None

    fig = go.Figure()
    for i, (_, row) in enumerate(sub.iterrows()):
        color = RADAR_COLORS[i % len(RADAR_COLORS)]
        y_vals, x_lbls, hover_text = [], [], []
        for lbl, col, unit in zip(labels, cols, units):
            v = row.get(col, np.nan)
            if pd.notna(v):
                y_vals.append(round(float(v), 3))
                x_lbls.append(lbl)
                hover_text.append(f'{lbl}: {v:.3f} {unit}')
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
    for label, col, color, unit in cfg['metrics']:
        vals = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
        if len(vals) > 0:
            val_display = f'{vals.mean():.3f}'
            sub_lbl = f'Promedio · n={len(vals)}'
            # mini barra de progreso (normalizada dentro del equipo)
            mn, mx = df[col].min(), df[col].max()
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
server = app.server
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
                  'border': f'1px solid {FAINT}', 'borderRadius': '12px',
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
                html.Div(id='pills-container',
                         style={'display': 'flex', 'flexWrap': 'wrap', 'flex': '1'}),
                html.Div([
                    html.Button('↩', id='btn-undo', n_clicks=0, title='Deshacer',
                                disabled=True,
                                style={'padding': '6px 10px', 'borderRadius': '8px',
                                       'background': 'transparent',
                                       'border': f'1px solid {FAINT}', 'color': MUTED,
                                       'fontSize': '14px', 'cursor': 'pointer',
                                       'marginRight': '6px', 'fontFamily': 'Inter,sans-serif'}),
                    html.Button('↺', id='btn-redo', n_clicks=0, title='Rehacer',
                                disabled=True,
                                style={'padding': '6px 10px', 'borderRadius': '8px',
                                       'background': 'transparent',
                                       'border': f'1px solid {FAINT}', 'color': MUTED,
                                       'fontSize': '14px', 'cursor': 'pointer',
                                       'marginRight': '6px', 'fontFamily': 'Inter,sans-serif'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginLeft': 'auto'}),
            ], style={'background': SURF, 'border': f'1px solid {FAINT}', 'borderRadius': '12px',
                      'padding': '13px 18px', 'marginBottom': '14px',
                      'display': 'flex', 'alignItems': 'center'}),

            html.Div(id='hist-crumb',
                     style={'fontSize': '11px', 'color': FAINT, 'marginBottom': '14px'}),

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
                        html.Span('= 1 desviación estándar por encima del promedio',
                                  style={'color': MUTED, 'fontSize': '12px'}),
                    ], style={'marginBottom': '8px'}),
                    html.Div([
                        html.Span('-1', style={'color': HOT, 'fontWeight': '700',
                                                'marginRight': '8px'}),
                        html.Span('= 1 desviación estándar por debajo del promedio',
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
                    html.Button('Drop Jump', id='jt-dj', n_clicks=0,
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
                        options=[{'label': pid, 'value': pid} for pid in ALL_IDS],
                        value=ALL_IDS[:3],   # primeros 3 por defecto
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
        ]),

        ], style={'flex': '1', 'minWidth': '0'}),

    ], style={'display': 'flex', 'gap': '20px', 'padding': '22px 28px',
              'maxWidth': '1500px', 'margin': '0 auto'}),

    # ── Stores ──
    dcc.Store(id='st-sel',  data=ALL_IDS),
    dcc.Store(id='st-hist', data=[ALL_IDS]),
    dcc.Store(id='st-hidx', data=0),
    dcc.Store(id='st-tab',  data='rend'),
    dcc.Store(id='st-jtab', data='cmj'),

], style={'background': BG, 'minHeight': '100vh', 'color': TEXT,
          'fontFamily': 'Inter,sans-serif'})


# ══════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════

# 1 · Selección de deportistas (rendimiento)
@app.callback(
    Output('st-sel',  'data'),
    Output('st-hist', 'data'),
    Output('st-hidx', 'data'),
    Input({'type': 'pill', 'index': ALL}, 'n_clicks'),
    Input('btn-undo', 'n_clicks'),
    Input('btn-redo', 'n_clicks'),
    State('st-sel',  'data'),
    State('st-hist', 'data'),
    State('st-hidx', 'data'),
    prevent_initial_call=True,
)
def update_selection(pill_clicks, undo, redo, cur, hist, hidx):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update
    tid = ctx.triggered[0]['prop_id']

    if 'btn-undo' in tid:
        if hidx > 0: hidx -= 1
        return hist[hidx], hist, hidx
    if 'btn-redo' in tid:
        if hidx < len(hist) - 1: hidx += 1
        return hist[hidx], hist, hidx

    pid = json.loads(tid.split('.')[0])['index']
    if pid == '__all__':
        new = ALL_IDS[:] if set(cur) != set(ALL_IDS) else [ALL_IDS[0]]
    else:
        new = list(cur)
        if pid in new:
            if len(new) > 1: new.remove(pid)
        else:
            new.append(pid)

    hist = hist[:hidx + 1] + [new]
    return new, hist, len(hist) - 1


# 2 · Pills
@app.callback(
    Output('pills-container', 'children'),
    Input('st-sel', 'data'),
)
def render_pills(sel):
    sel_set = set(sel)
    all_on  = sel_set == set(ALL_IDS)

    def pill_style(active, color=None):
        base = {'padding': '5px 12px', 'borderRadius': '20px', 'fontSize': '12px',
                'fontWeight': '500', 'cursor': 'pointer', 'fontFamily': 'Inter,sans-serif',
                'marginRight': '4px', 'marginBottom': '4px', 'transition': 'all .2s',
                'border': '1px solid'}
        if active and color:
            base.update({'borderColor': color, 'background': color + '22', 'color': color})
        elif active:
            base.update({'borderColor': TEXT, 'background': SURF3, 'color': TEXT})
        else:
            base.update({'borderColor': FAINT, 'background': 'transparent', 'color': MUTED})
        return base

    pills = [html.Button('Todos', id={'type': 'pill', 'index': '__all__'},
                         n_clicks=0, style=pill_style(all_on))]
    for pid in ALL_IDS:
        row   = df[df['Nombre'] == pid].iloc[0]
        color = nc(row['Nivel'])
        pills.append(html.Button(
            pid, id={'type': 'pill', 'index': pid},
            n_clicks=0, style=pill_style(pid in sel_set, color)
        ))
    return pills


# 3 · Charts + stats + crumb + undo/redo
@app.callback(
    Output('chart-radar', 'figure'),
    Output('chart-bar',   'figure'),
    Output('stats-row',   'children'),
    Output('hist-crumb',  'children'),
    Output('btn-undo',    'disabled'),
    Output('btn-redo',    'disabled'),
    Input('st-sel',  'data'),
    Input('st-hidx', 'data'),
    State('st-hist', 'data'),
)
def update_charts(sel, hidx, hist):
    sub = df[df['Nombre'].isin(sel)].sort_values('Overall', ascending=False)
    n   = len(sub)
    avg = sub['Overall'].mean() if n else 0

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
        xs=6, md=True, className='g-2')

    counts = sub['Nivel'].value_counts()
    stats  = [
        stat_card(n, 'Total deportistas', COOL, '👥'),
        stat_card(counts.get('Alto', 0),  'Nivel alto',  TEAL, '↗'),
        stat_card(counts.get('Medio', 0), 'Nivel medio', GOLD, '='),
        stat_card(counts.get('Bajo', 0),  'Nivel bajo',  HOT,  '↓'),
        stat_card(3, 'Métricas evaluadas', '#8B5CF6', '◈'),
    ]

    lbl   = ('todos' if n == len(ALL_IDS) else f'{n} deportista{"s" if n > 1 else ""}')
    crumb = [html.Span('Vista actual: ', style={'color': FAINT}),
             html.Span(lbl, style={'color': MUTED})]

    return (fig_radar(sub), fig_bar(sub), stats, crumb,
            hidx == 0, hidx >= len(hist) - 1)


# 4 · Detalle al clic en barra
@app.callback(
    Output('detail-wrap', 'children'),
    Input('chart-bar', 'clickData'),
)
def show_detail(click):
    if not click:
        return html.Div([
            html.Div('○', style={'fontSize': '24px', 'color': FAINT, 'marginBottom': '6px'}),
            html.Div('Selecciona un deportista en el gráfico para ver su detalle',
                     style={'fontSize': '13px', 'color': FAINT}),
        ], style={'display': 'flex', 'flexDirection': 'column',
                  'alignItems': 'center', 'justifyContent': 'center', 'minHeight': '110px'})

    pid  = click['points'][0]['y']
    rows = df[df['Nombre'] == pid]
    if rows.empty:
        return no_update
    return detail_card(rows.iloc[0])

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

    # Determinar sub-tab activo
    if 'jt-cmj' in tid:
        tab = 'cmj'
    elif 'jt-sj' in tid:
        tab = 'sj'
    elif 'jt-dj' in tid:
        tab = 'dj'
    else:
        tab = cur_tab  # cambio de jugadores, mantener tab

    sel = player_sel or ALL_IDS[:3]

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
    app.run(debug=False, port=8050)
