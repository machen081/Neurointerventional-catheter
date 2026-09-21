import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io
import copy

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

st.set_page_config(page_title="微导管多层结构分析", layout="wide")

# ==================== 材料库 ====================
MATERIAL_LIBRARY_NORMAL = {
    "自定义": None,
    "PTFE (块体)": {"E": 500.0, "sigma": 106.2},
    "PTFE (挤出管)": {"E": 200.0, "sigma": 80.5},
    "Pebax 2533": {"E": 12.0, "sigma": 15.0},
    "Pebax 3533": {"E": 20.0, "sigma": 20.0},
    "Pebax 5533": {"E": 30.0, "sigma": 25.0},
    "Pebax 6333": {"E": 40.0, "sigma": 28.0},
    "Pebax 7233": {"E": 50.0, "sigma": 30.0},
    "尼龙 12": {"E": 1500.0, "sigma": 45.0},
    "尼龙 6": {"E": 2500.0, "sigma": 70.0},
    "聚氨酯": {"E": 30.0, "sigma": 30.0},
    "聚乙烯 (HDPE)": {"E": 900.0, "sigma": 25.0},
}

MATERIAL_LIBRARY_WIRE = {
    "自定义": None,
    "不锈钢 304 (冷加工)": {"E_f": 193000.0, "sigma_f": 2200.0},
    "不锈钢 316LVM (冷加工)": {"E_f": 193000.0, "sigma_f": 2400.0},
    "镍钛合金 (超弹)": {"E_f": 60000.0, "sigma_f": 1200.0},
    "钴铬合金 (L605)": {"E_f": 220000.0, "sigma_f": 2500.0},
    "铂钨合金": {"E_f": 170000.0, "sigma_f": 800.0},
}

LAYER_TYPES = {
    '普通材料': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '弹性模量(MPa)', '抗拉强度(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.27, '外半径(mm)': 0.3048,
                    '弹性模量(MPa)': 400.0, '抗拉强度(MPa)': 106.2},
        'caption': '普通材料：各向同性，E_z = E_θ'
    },
    '编织层': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '扁丝宽度(mm)', '扁丝厚度(mm)', '股数', '每束根数',
                    '每英寸交叉数', '丝材模量(MPa)', '丝材抗拉强度(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                    '扁丝宽度(mm)': 0.05, '扁丝厚度(mm)': 0.02,
                    '股数': 16, '每束根数': 1, '每英寸交叉数': 80,
                    '丝材模量(MPa)': 193000.0, '丝材抗拉强度(MPa)': 2200.0,
                    '原始基体体积分数': 0.0},
        'caption': '编织层：抗拉力 = 丝材贡献 + 热熔填充贡献'
    },
    '弹簧圈': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '丝径(mm)', '螺距(mm)', '丝材模量(MPa)', '丝材抗拉强度(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                    '丝径(mm)': 0.0254, '螺距(mm)': 0.15,
                    '丝材模量(MPa)': 193000.0, '丝材抗拉强度(MPa)': 2200.0,
                    '原始基体体积分数': 0.0},
        'caption': '弹簧圈：抗拉力 = 弹簧公式 + 热熔填充贡献'
    },
}

def make_default_layer(layer_type, L_total=30, r_in=0.27, r_out=0.3048):
    d = LAYER_TYPES[layer_type]['default'].copy()
    d['结束位置(mm)'] = L_total
    d['内半径(mm)'] = r_in
    d['外半径(mm)'] = r_out
    return pd.DataFrame([d])

def create_default_structure(L_total=30):
    return [
        {'name': 'Hot Melt', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                                '内半径(mm)': 0.33, '外半径(mm)': 0.4,
                                '弹性模量(MPa)': 12.0, '抗拉强度(MPa)': 15.0}])},
        {'name': 'Braid', 'type': '弹簧圈',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                                '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                                '丝径(mm)': 0.0254, '螺距(mm)': 0.15,
                                '丝材模量(MPa)': 193000.0, '丝材抗拉强度(MPa)': 2200.0,
                                '原始基体体积分数': 0.0}])},
        {'name': 'Coil', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                                '内半径(mm)': 0.27, '外半径(mm)': 0.3048,
                                '弹性模量(MPa)': 400.0, '抗拉强度(MPa)': 106.2}])},
    ]

def normalize_structure(structure):
    for layer in structure:
        if not isinstance(layer, dict) or 'data' not in layer:
            continue
        df = layer['data']
        if not isinstance(df, pd.DataFrame):
            try:
                if isinstance(df, list):
                    df = pd.DataFrame(df)
                elif isinstance(df, dict):
                    df = pd.DataFrame([df])
                else:
                    df = pd.DataFrame()
            except Exception:
                df = pd.DataFrame()
            layer['data'] = df
        if df.empty:
            layer['data'] = make_default_layer(layer.get('type', '普通材料'))
            continue
        expected_cols = LAYER_TYPES[layer['type']]['columns']
        if list(df.columns) != expected_cols:
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = LAYER_TYPES[layer['type']]['default'].get(col, 0.0)
            layer['data'] = df[expected_cols]
    return structure

# ==================== 会话状态 ====================
CURRENT_VERSION = "v26_manual_calib"

if 'structure_version' not in st.session_state or st.session_state.structure_version != CURRENT_VERSION:
    st.session_state.structure = create_default_structure()
    st.session_state.structure_version = CURRENT_VERSION
    st.session_state.L_total = 30.0
    st.session_state.x_pos = 0.0
    st.session_state.ea_correction = 1.0
    st.session_state.kp_correction = 1.0
    st.session_state.span_L = 30.0
    st.session_state.eta_bond = 0.8
    st.session_state.softening_c = 1.0
    st.session_state.saved_schemes = []
else:
    st.session_state.structure = normalize_structure(st.session_state.structure)

if 'L_total' not in st.session_state: st.session_state.L_total = 30.0
if 'x_pos' not in st.session_state: st.session_state.x_pos = 0.0
if 'ea_correction' not in st.session_state: st.session_state.ea_correction = 1.0
if 'kp_correction' not in st.session_state: st.session_state.kp_correction = 1.0
if 'span_L' not in st.session_state: st.session_state.span_L = 30.0
if 'eta_bond' not in st.session_state: st.session_state.eta_bond = 0.8
if 'softening_c' not in st.session_state: st.session_state.softening_c = 1.0
if 'saved_schemes' not in st.session_state: st.session_state.saved_schemes = []

# ==================== 分段查找 ====================
def find_segment(df, x):
    if df is None or df.empty:
        return None
    for _, row in df.iterrows():
        try:
            if row['起始位置(mm)'] <= x <= row['结束位置(mm)']:
                return row
        except Exception:
            continue
    return None

def find_hot_melt_props(structure, x):
    candidates = []
    for layer in structure:
        row = find_segment(layer['data'], x)
        if row is None:
            continue
        if layer['type'] == '普通材料':
            try:
                candidates.append((row['外半径(mm)'], row['弹性模量(MPa)'],
                                   row.get('抗拉强度(MPa)', 0.0)))
            except KeyError:
                continue
    if not candidates:
        return None, None
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1], candidates[0][2]

def find_hot_melt_E(structure, x):
    E, _ = find_hot_melt_props(structure, x)
    return E

def get_reference_radius(structure, layer_type_name):
    refs = []
    for layer in structure:
        if layer['type'] != layer_type_name:
            continue
        df = layer['data']
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            try:
                refs.append((row['内半径(mm)'], row['外半径(mm)']))
            except Exception:
                continue
    if not refs:
        return None
    return (float(np.median([r[0] for r in refs])), float(np.median([r[1] for r in refs])))

# ==================== 编织角 ====================
def compute_braid_angle(r_in, r_out, PPI, N_strands):
    D_mid = r_in + r_out
    if N_strands <= 0 or D_mid <= 0:
        return 45.0
    val = np.pi * D_mid * PPI / (25.4 * N_strands)
    return np.degrees(np.arctan(val))

# ==================== 编织层模量 ====================
def compute_braid_moduli(row, E_hm):
    if E_hm is None: E_hm = 0.0
    w = row['扁丝宽度(mm)']; t = row['扁丝厚度(mm)']
    N = row['股数']; n_s = row['每束根数']
    PPI = row['每英寸交叉数']; E_f = row['丝材模量(MPa)']
    r_in, r_out = row['内半径(mm)'], row['外半径(mm)']
    V_matrix = row.get('原始基体体积分数', 0.0)

    alpha = compute_braid_angle(r_in, r_out, PPI, N)
    alpha_rad = np.radians(alpha)

    denom = np.pi * (r_out**2 - r_in**2) * np.cos(alpha_rad)
    V_f = min(1.0, 2 * N * n_s * w * t / denom) if denom > 0 else 0.0
    V_void = max(0.0, 1.0 - V_f - V_matrix)
    E_m_eff = E_hm * V_void / (V_void + V_matrix) if (V_void + V_matrix) > 0 else 0.0

    E_z = E_f * V_f * (np.cos(alpha_rad)**4) + E_m_eff * (1 - V_f)
    E_theta = E_f * V_f * (np.sin(alpha_rad)**4) + E_m_eff * (1 - V_f)
    return E_z, E_theta, V_f, V_void, alpha

# ==================== 弹簧圈模量 ====================
def compute_coil_moduli(row, E_hm):
    if E_hm is None: E_hm = 0.0
    d = row['丝径(mm)']; pitch = row['螺距(mm)']
    E_f = row['丝材模量(MPa)']
    r_in, r_out = row['内半径(mm)'], row['外半径(mm)']
    V_matrix = row.get('原始基体体积分数', 0.0)

    nu = 0.3
    G = E_f / (2 * (1 + nu))
    D = r_in + r_out
    A = np.pi * (r_out**2 - r_in**2)

    if pitch > 0 and r_out > r_in:
        V_spring = min(1.0, (np.pi * d**2 / 4) / (pitch * (r_out - r_in)))
    else:
        V_spring = 0.0

    V_void = max(0.0, 1.0 - V_spring - V_matrix)
    E_m_eff = E_hm * V_void / (V_void + V_matrix) if (V_void + V_matrix) > 0 else 0.0

    if D > 0 and A > 0 and pitch > 0:
        E_spring_axial = G * d**4 * pitch / (8 * D**3 * A)
    else:
        E_spring_axial = 0.0
    E_z = E_spring_axial + E_m_eff * (1 - V_spring)
    E_theta = E_f * V_spring + E_m_eff * (1 - V_spring)
    return E_z, E_theta, V_spring, V_void

# ==================== 弹簧抗拉力 ====================
def compute_coil_tensile_force(sigma_uts, d_wire, pitch, r_in, r_out):
    D = r_in + r_out
    if D <= 0 or d_wire <= 0:
        return 0.0
    beta_factor = 1.0 / np.sqrt(1.0 + (pitch / (np.pi * D))**2) if pitch > 0 else 1.0
    Fu = sigma_uts * np.pi * d_wire**3 / (8.0 * D) * beta_factor
    return Fu

# ==================== 截面生成 ====================
def compute_at_x(structure, x, eta_bond=1.0):
    hot_melt_E, hot_melt_sigma = find_hot_melt_props(structure, x)
    layers = []
    has_braid_here = False
    has_coil_here = False

    for idx, layer in enumerate(structure):
        row = find_segment(layer['data'], x)
        if row is None:
            continue
        ltype = layer['type']
        if ltype == '编织层': has_braid_here = True
        elif ltype == '弹簧圈': has_coil_here = True
        try:
            alpha = None; V_void = None
            Fu_override = None
            Fu_fiber = 0.0
            Fu_matrix_contrib = 0.0
            r_in_v = row['内半径(mm)']
            r_out_v = row['外半径(mm)']
            A_total = np.pi * (r_out_v**2 - r_in_v**2)

            if ltype == '普通材料':
                E_z = row['弹性模量(MPa)']
                E_theta = E_z
                V_f = None
                sigma_uts = row.get('抗拉强度(MPa)', 0.0)
            elif ltype == '编织层':
                E_z, E_theta, V_f, V_void, alpha = compute_braid_moduli(row, hot_melt_E)
                sigma_uts = row.get('丝材抗拉强度(MPa)', 0.0)
                V_f_val = V_f if V_f is not None else 0.0
                Fu_fiber = sigma_uts * A_total * V_f_val
                V_matrix = row.get('原始基体体积分数', 0.0)
                if hot_melt_sigma is not None:
                    Fu_matrix_contrib = hot_melt_sigma * A_total * (1.0 - V_f_val - V_matrix) * eta_bond
                Fu_override = Fu_fiber + Fu_matrix_contrib
            elif ltype == '弹簧圈':
                E_z, E_theta, V_f, V_void = compute_coil_moduli(row, hot_melt_E)
                sigma_uts = row.get('丝材抗拉强度(MPa)', 0.0)
                Fu_fiber = compute_coil_tensile_force(
                    sigma_uts, row['丝径(mm)'], row['螺距(mm)'], r_in_v, r_out_v)
                V_spring = V_f if V_f is not None else 0.0
                V_matrix = row.get('原始基体体积分数', 0.0)
                if hot_melt_sigma is not None:
                    Fu_matrix_contrib = hot_melt_sigma * A_total * (1.0 - V_spring - V_matrix) * eta_bond
                Fu_override = Fu_fiber + Fu_matrix_contrib
            else:
                continue
        except KeyError:
            continue
        layers.append({
            'name': layer['name'], 'type': ltype,
            'r_in': r_in_v, 'r_out': r_out_v,
            'E_z': E_z, 'E_theta': E_theta, 'V_f': V_f, 'V_void': V_void,
            'alpha': alpha, 'sigma_uts': float(sigma_uts),
            'Fu_override': Fu_override,
            'Fu_fiber': Fu_fiber, 'Fu_matrix': Fu_matrix_contrib,
            'layer_idx': idx, 'is_filler': False
        })

    def is_occupied(r_in_ref, r_out_ref, tol=0.005):
        for l in layers:
            overlap = min(r_out_ref, l['r_out']) - max(r_in_ref, l['r_in'])
            if overlap > tol: return True
        return False

    if not has_braid_here:
        braid_ref = get_reference_radius(structure, '编织层')
        if braid_ref is not None and hot_melt_E is not None:
            r_in_ref, r_out_ref = braid_ref
            if not is_occupied(r_in_ref, r_out_ref):
                layers.append({'name': 'Hot Melt (braid filler)', 'type': '普通材料',
                               'r_in': r_in_ref, 'r_out': r_out_ref,
                               'E_z': hot_melt_E, 'E_theta': hot_melt_E,
                               'V_f': None, 'V_void': None, 'alpha': None,
                               'sigma_uts': hot_melt_sigma if hot_melt_sigma else 15.0,
                               'Fu_override': None, 'Fu_fiber': 0.0, 'Fu_matrix': 0.0,
                               'layer_idx': -2, 'is_filler': True})

    if not has_coil_here:
        coil_ref = get_reference_radius(structure, '弹簧圈')
        if coil_ref is not None and hot_melt_E is not None:
            r_in_ref, r_out_ref = coil_ref
            if not is_occupied(r_in_ref, r_out_ref):
                layers.append({'name': 'Hot Melt (coil filler)', 'type': '普通材料',
                               'r_in': r_in_ref, 'r_out': r_out_ref,
                               'E_z': hot_melt_E, 'E_theta': hot_melt_E,
                               'V_f': None, 'V_void': None, 'alpha': None,
                               'sigma_uts': hot_melt_sigma if hot_melt_sigma else 15.0,
                               'Fu_override': None, 'Fu_fiber': 0.0, 'Fu_matrix': 0.0,
                               'layer_idx': -1, 'is_filler': True})

    layers.sort(key=lambda l: -l['r_out'])
    return layers

# ==================== 管壁刚度 ====================
def compute_wall_bending_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    if t <= 0: return 0.0
    if r_in <= 1e-9 or r_in / r_out < 0.5:
        return E_theta * t**3 / 12
    r_n = t / np.log(r_out / r_in)
    e = (r_out + r_in) / 2 - r_n
    return E_theta * t * e * r_n

def compute_wall_axial_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    return E_theta * t if t > 0 else 0.0

# ==================== 刚度计算 ====================
def compute_stiffness(layers, ea_corr=1.0, kp_corr=1.0):
    EA_c, EI_c = [], []
    EI_theta_bend_c, EA_theta_c = [], []

    for l in layers:
        r_in, r_out = l['r_in'], l['r_out']
        E_z = l['E_z']; E_theta = l.get('E_theta', E_z)
        A_i = np.pi * (r_out**2 - r_in**2)

        EA_c.append(E_z * A_i)
        EI_c.append((np.pi / 4) * E_z * (r_out**4 - r_in**4))
        EI_theta_bend_c.append(compute_wall_bending_stiffness(E_theta, r_in, r_out))
        EA_theta_c.append(compute_wall_axial_stiffness(E_theta, r_in, r_out))

    EA = sum(EA_c) * ea_corr
    EI = sum(EI_c)
    EI_theta_bend = sum(EI_theta_bend_c)
    EA_theta = sum(EA_theta_c)

    if layers:
        r0 = min(l['r_in'] for l in layers)
        rn = max(l['r_out'] for l in layers)
        R = (r0 + rn) / 2
        thick_ratio = (rn - r0) / R if R > 0 else 0
        const = np.pi/4 - 2/np.pi

        if thick_ratio < 0.1:
            Kp_raw = EI_theta_bend / (R**3 * const) if EI_theta_bend > 0 else 0.0
            model_used = "thin-wall"
        else:
            compliance = 0.0
            if EI_theta_bend > 0: compliance += const * R**3 / EI_theta_bend
            if EA_theta > 0: compliance += const * R / EA_theta
            Kp_raw = 1.0 / compliance if compliance > 0 else 0.0
            model_used = "thick-wall"

        Kp = Kp_raw * kp_corr
        Kp_c = [ei / EI_theta_bend * Kp for ei in EI_theta_bend_c] if EI_theta_bend > 0 else [0.0]*len(layers)
    else:
        Kp = 0.0; Kp_c = []; model_used = "N/A"; thick_ratio = 0.0

    return EA, EI, Kp, EA_c, EI_c, Kp_c, model_used, thick_ratio

# ==================== 强度计算 ====================
def compute_axial_strength(layers):
    Fu_layer = []
    for l in layers:
        r_in, r_out = l['r_in'], l['r_out']
        A_i = np.pi * (r_out**2 - r_in**2)
        sigma_uts = l.get('sigma_uts', 0.0)
        if l.get('Fu_override') is not None:
            Fu_layer.append(l['Fu_override'])
        else:
            V_f = l.get('V_f')
            if V_f is None: V_f = 1.0
            Fu_layer.append(sigma_uts * A_i * V_f)
    return sum(Fu_layer), Fu_layer

def compute_bending_yield(layers):
    if not layers:
        return 0.0, None, []
    EI_total = sum(
        l['E_z'] * (np.pi/4) * (l['r_out']**4 - l['r_in']**4)
        for l in layers
    )
    if EI_total <= 0:
        return 0.0, None, []

    candidates = []
    for l in layers:
        E_i = l['E_z']
        r_out = l['r_out']
        sigma_uts = l.get('sigma_uts', 0.0)
        if E_i > 0 and r_out > 0 and sigma_uts > 0:
            M_i = sigma_uts * EI_total / (E_i * r_out)
            candidates.append({'layer': l['name'], 'M_y': M_i, 'E_z': E_i,
                               'r_out': r_out, 'sigma_uts': sigma_uts})

    if not candidates:
        return 0.0, None, []
    candidates.sort(key=lambda c: c['M_y'])
    return candidates[0]['M_y'], candidates[0]['layer'], candidates

def compute_collapse_force(layers):
    if not layers:
        return 0.0, None, []
    EI_theta_total = sum(
        compute_wall_bending_stiffness(l['E_theta'], l['r_in'], l['r_out'])
        for l in layers
    )
    if EI_theta_total <= 0:
        return 0.0, None, []

    r0 = min(l['r_in'] for l in layers)
    rn = max(l['r_out'] for l in layers)
    R = (r0 + rn) / 2
    C = 0.318

    candidates = []
    for l in layers:
        E_theta = l['E_theta']
        t_i = l['r_out'] - l['r_in']
        sigma_uts = l.get('sigma_uts', 0.0)
        if E_theta > 0 and t_i > 0 and R > 0 and sigma_uts > 0:
            F_i = sigma_uts * EI_theta_total * 2 / (E_theta * C * R * t_i)
            candidates.append({'layer': l['name'], 'F_c': F_i, 'E_theta': E_theta,
                               't': t_i, 'sigma_uts': sigma_uts})

    if not candidates:
        return 0.0, None, []
    candidates.sort(key=lambda c: c['F_c'])
    return candidates[0]['F_c'], candidates[0]['layer'], candidates

# ==================== 非线性力-位移模型 ====================
def compute_crush_force_nonlinear(Kp, D_outer, dD, c=1.0):
    if D_outer <= 0:
        return Kp * dD
    dD = np.asarray(dD)
    return Kp * dD / (1.0 + c * dD / D_outer)

# ==================== 沿长度扫描 ====================
def compute_along_length(structure, L_total, ea_corr=1.0, kp_corr=1.0, eta_bond=1.0, n=200):
    xs = np.linspace(0, L_total, n)
    EA_arr = np.zeros(n); EI_arr = np.zeros(n); Kp_arr = np.zeros(n)
    Fu_arr = np.zeros(n); My_arr = np.zeros(n); Fc_arr = np.zeros(n)
    for i, x in enumerate(xs):
        layers = compute_at_x(structure, x, eta_bond=eta_bond)
        EA, EI, Kp, _, _, _, _, _ = compute_stiffness(layers, ea_corr, kp_corr)
        Fu, _ = compute_axial_strength(layers)
        My, _, _ = compute_bending_yield(layers)
        Fc, _, _ = compute_collapse_force(layers)
        EA_arr[i] = EA; EI_arr[i] = EI; Kp_arr[i] = Kp
        Fu_arr[i] = Fu; My_arr[i] = My; Fc_arr[i] = Fc
    return xs, EA_arr, EI_arr, Kp_arr, Fu_arr, My_arr, Fc_arr

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("导管结构定义")
    L_total = st.number_input("导管总长度 (mm)", min_value=1.0, value=st.session_state.L_total, step=10.0)
    st.session_state.L_total = L_total

    st.markdown("**层顺序：列表第一个为最外层**")

    with st.expander("➕ 添加新层"):
        new_type = st.selectbox("层类型", list(LAYER_TYPES.keys()), key="new_type")
        insert_pos = st.number_input("插入位置（0=最外，末尾=最内）", min_value=0,
                                     max_value=len(st.session_state.structure),
                                     value=len(st.session_state.structure), step=1, key="insert_pos")
        if st.button("添加层", key="add_layer_btn"):
            if st.session_state.structure:
                r_out_ref = st.session_state.structure[0]['data'].iloc[0]['外半径(mm)']
                r_in_ref = st.session_state.structure[-1]['data'].iloc[0]['内半径(mm)']
            else:
                r_out_ref, r_in_ref = 0.4, 0.27
            new_layer = {'name': f'Layer {len(st.session_state.structure)+1}',
                         'type': new_type,
                         'data': make_default_layer(new_type, L_total, r_in_ref, r_out_ref)}
            st.session_state.structure.insert(int(insert_pos), new_layer)
            st.rerun()

    st.markdown("---")
    st.markdown("**编辑各层**")

    for i, layer in enumerate(st.session_state.structure):
        with st.expander(f"第{i+1}层：{layer['name']}（{layer['type']}）", expanded=False):
            if layer['type'] == '普通材料':
                mat_options = list(MATERIAL_LIBRARY_NORMAL.keys())
                selected_mat = st.selectbox("📚 材料库（室温典型值）", mat_options, key=f"mat_select_{i}")
                df_cur = layer['data']
                n_rows = len(df_cur)
                if n_rows > 0 and selected_mat != "自定义":
                    seg_labels = ["🎯 全部段"] + [
                        f"第 {j+1} 段 ({df_cur.iloc[j]['起始位置(mm)']:.1f} ~ {df_cur.iloc[j]['结束位置(mm)']:.1f} mm)"
                        for j in range(n_rows)
                    ]
                    selected_seg = st.selectbox("应用范围", seg_labels, key=f"seg_select_{i}")
                else:
                    selected_seg = "🎯 全部段"

                col_a, col_b = st.columns([1, 2])
                with col_a:
                    if st.button("填入", key=f"apply_mat_{i}") and selected_mat != "自定义":
                        mat = MATERIAL_LIBRARY_NORMAL[selected_mat]
                        df_new = layer['data'].copy()
                        if len(df_new) > 0:
                            if selected_seg == "🎯 全部段":
                                df_new['弹性模量(MPa)'] = mat['E']
                                df_new['抗拉强度(MPa)'] = mat['sigma']
                            else:
                                seg_idx = seg_labels.index(selected_seg) - 1
                                df_new.loc[df_new.index[seg_idx], '弹性模量(MPa)'] = mat['E']
                                df_new.loc[df_new.index[seg_idx], '抗拉强度(MPa)'] = mat['sigma']
                            layer['data'] = df_new
                            st.rerun()
                with col_b:
                    if selected_mat != "自定义":
                        st.caption(f"E = {MATERIAL_LIBRARY_NORMAL[selected_mat]['E']} MPa, σ_uts = {MATERIAL_LIBRARY_NORMAL[selected_mat]['sigma']} MPa")

            elif layer['type'] in ('编织层', '弹簧圈'):
                mat_options = list(MATERIAL_LIBRARY_WIRE.keys())
                selected_mat = st.selectbox("📚 丝材库（室温典型值）", mat_options, key=f"mat_select_{i}")
                df_cur = layer['data']
                n_rows = len(df_cur)
                if n_rows > 0 and selected_mat != "自定义":
                    seg_labels = ["🎯 全部段"] + [
                        f"第 {j+1} 段 ({df_cur.iloc[j]['起始位置(mm)']:.1f} ~ {df_cur.iloc[j]['结束位置(mm)']:.1f} mm)"
                        for j in range(n_rows)
                    ]
                    selected_seg = st.selectbox("应用范围", seg_labels, key=f"seg_select_{i}")
                else:
                    selected_seg = "🎯 全部段"

                col_a, col_b = st.columns([1, 2])
                with col_a:
                    if st.button("填入", key=f"apply_mat_{i}") and selected_mat != "自定义":
                        mat = MATERIAL_LIBRARY_WIRE[selected_mat]
                        df_new = layer['data'].copy()
                        if len(df_new) > 0:
                            if selected_seg == "🎯 全部段":
                                df_new['丝材模量(MPa)'] = mat['E_f']
                                df_new['丝材抗拉强度(MPa)'] = mat['sigma_f']
                            else:
                                seg_idx = seg_labels.index(selected_seg) - 1
                                df_new.loc[df_new.index[seg_idx], '丝材模量(MPa)'] = mat['E_f']
                                df_new.loc[df_new.index[seg_idx], '丝材抗拉强度(MPa)'] = mat['sigma_f']
                            layer['data'] = df_new
                            st.rerun()
                with col_b:
                    if selected_mat != "自定义":
                        st.caption(f"E_f = {MATERIAL_LIBRARY_WIRE[selected_mat]['E_f']} MPa, σ_f = {MATERIAL_LIBRARY_WIRE[selected_mat]['sigma_f']} MPa")

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                new_name = st.text_input("名称（图表中显示）", value=layer['name'], key=f"name_{i}")
                if new_name != layer['name']:
                    layer['name'] = new_name
            with col2:
                new_type = st.selectbox("类型", list(LAYER_TYPES.keys()),
                                        index=list(LAYER_TYPES.keys()).index(layer['type']), key=f"type_{i}")
                if new_type != layer['type']:
                    old = layer['data'].iloc[0].to_dict() if len(layer['data']) > 0 else {}
                    r_in = old.get('内半径(mm)', 0.27); r_out = old.get('外半径(mm)', 0.3048)
                    start = old.get('起始位置(mm)', 0.0); end = old.get('结束位置(mm)', L_total)
                    layer['type'] = new_type
                    layer['data'] = make_default_layer(new_type, end, r_in, r_out)
                    layer['data'].loc[0, '起始位置(mm)'] = start
                    st.rerun()
            with col3:
                if st.button("删除", key=f"del_{i}"):
                    st.session_state.structure.pop(i)
                    st.rerun()

            st.caption(LAYER_TYPES[layer['type']]['caption'])

            edited = st.data_editor(
                layer['data'],
                num_rows="dynamic",
                use_container_width=True,
                key=f"data_{i}_v26"
            )
            if edited is not None and not edited.empty:
                layer['data'] = edited.copy()

    st.markdown("---")
    st.markdown("**刚度修正系数**")
    ea_correction = st.number_input("轴向刚度 EA 修正系数", min_value=0.01, max_value=2.0,
                                    value=float(st.session_state.ea_correction),
                                    step=0.05, format="%.2f", key="ea_corr_input")
    st.session_state.ea_correction = ea_correction

    kp_correction = st.number_input("抗压扁刚度 Kp 修正系数", min_value=0.01, max_value=10.0,
                                    value=float(st.session_state.kp_correction),
                                    step=0.01, format="%.3f", key="kp_corr_input")
    st.session_state.kp_correction = kp_correction

    st.markdown("---")
    st.markdown("**抗压扁非线性参数**")
    softening_c = st.number_input(
        "软化系数 c（越大越软）",
        min_value=0.0, max_value=10.0,
        value=float(st.session_state.softening_c),
        step=0.1, format="%.2f",
        key="softening_c_input"
    )
    st.session_state.softening_c = softening_c
    st.caption(
        "c = 0：完全线性（旧行为）\n"
        "c = 1：中等软化（默认）\n"
        "c = 3：强软化（薄壁易压溃）\n"
        "公式：F = Kp·ΔD / (1 + c·ΔD/D)"
    )

    st.markdown("---")
    st.markdown("**抗拉强度参数**")
    eta_bond = st.number_input("热熔填充与丝材的粘接系数 η", min_value=0.0, max_value=1.0,
                               value=float(st.session_state.eta_bond),
                               step=0.05, format="%.2f", key="eta_bond_input")
    st.session_state.eta_bond = eta_bond
    st.caption("η=1 完全粘接；η<1 有滑移折减。默认 0.8。")

    st.markdown("---")
    st.markdown("**三点弯曲试验参数**")
    span_L = st.number_input("三点弯曲跨距 L (mm)", min_value=1.0, max_value=200.0,
                             value=float(st.session_state.span_L),
                             step=1.0, key="span_L_input")
    st.session_state.span_L = span_L

    st.markdown("---")
    st.markdown("**💾 方案管理**")

    scheme_name = st.text_input("方案名称", value=f"Scheme {len(st.session_state.saved_schemes)+1}",
                                key="scheme_name_input")

    col_save, col_clear = st.columns([1, 1])
    with col_save:
        if st.button("💾 保存当前方案", key="save_scheme_btn", type="primary"):
            scheme = {
                'name': scheme_name,
                'structure': copy.deepcopy(st.session_state.structure),
                'L_total': L_total,
                'ea_correction': ea_correction,
                'kp_correction': kp_correction,
                'eta_bond': eta_bond,
                'softening_c': softening_c,
                'span_L': span_L
            }
            existing_idx = None
            for idx, s in enumerate(st.session_state.saved_schemes):
                if s['name'] == scheme_name:
                    existing_idx = idx
                    break
            if existing_idx is not None:
                st.session_state.saved_schemes[existing_idx] = scheme
                st.success(f"已覆盖方案：{scheme_name}")
            else:
                st.session_state.saved_schemes.append(scheme)
                st.success(f"已保存方案：{scheme_name}")
            st.rerun()
    with col_clear:
        if st.button("🗑️ 清空所有方案", key="clear_schemes_btn"):
            st.session_state.saved_schemes = []
            st.rerun()

    if st.session_state.saved_schemes:
        st.markdown(f"**已保存 {len(st.session_state.saved_schemes)} 个方案：**")
        for idx, s in enumerate(st.session_state.saved_schemes):
            col_name, col_load, col_del = st.columns([3, 1, 1])
            with col_name:
                st.caption(f"{idx+1}. {s['name']} (Kp_corr={s['kp_correction']:.2f}, c={s['softening_c']:.2f})")
            with col_load:
                if st.button("载入", key=f"load_scheme_{idx}"):
                    st.session_state.structure = copy.deepcopy(s['structure'])
                    st.session_state.L_total = s['L_total']
                    st.session_state.ea_correction = s['ea_correction']
                    st.session_state.kp_correction = s['kp_correction']
                    st.session_state.eta_bond = s['eta_bond']
                    st.session_state.softening_c = s['softening_c']
                    st.session_state.span_L = s['span_L']
                    for k in list(st.session_state.keys()):
                        if k.startswith("data_") or k.startswith("name_") or k.startswith("type_"):
                            del st.session_state[k]
                    st.rerun()
            with col_del:
                if st.button("删除", key=f"del_scheme_{idx}"):
                    st.session_state.saved_schemes.pop(idx)
                    st.rerun()

    st.markdown("---")
    if st.button("🔄 强制刷新计算", key="refresh_btn"):
        st.rerun()

    if st.button("恢复示例数据", key="reset_btn"):
        keys_to_clear = [k for k in list(st.session_state.keys())
                         if k.startswith("data_") or k.startswith("name_") or k.startswith("type_")
                         or k.startswith("mat_select_") or k.startswith("seg_select_")
                         or k.startswith("apply_mat_")
                         or k in ("ea_corr_input", "kp_corr_input", "span_L_input", "eta_bond_input",
                                  "softening_c_input", "new_type", "insert_pos", "add_layer_btn")]
        for k in keys_to_clear:
            del st.session_state[k]
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.session_state.ea_correction = 1.0
        st.session_state.kp_correction = 1.0
        st.session_state.span_L = 30.0
        st.session_state.eta_bond = 0.8
        st.session_state.softening_c = 1.0
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层结构分析")

st.caption(
    "**单位约定** — 长度: mm | 弹性模量/抗拉强度: MPa | 力: N | "
    "轴向刚度 EA: N | 弯曲刚度 EI: N·mm² | 抗压扁刚度 Kp: N/mm | 力矩 My: N·mm"
)

# ============================================================
# 📖 使用说明书
# ============================================================
with st.expander("📖 使用说明书（点击展开）", expanded=False):
    st.markdown("""
# 目录

1. [快速开始](#一快速开始)
2. [界面总览](#二界面总览)
3. [输入参数详解](#三输入参数详解)
4. [材料库使用](#四材料库使用)
5. [刚度分析](#五刚度分析)
6. [强度分析](#六强度分析)
7. [非线性力-位移曲线](#七非线性力-位移曲线)
8. [修正系数详解](#八修正系数详解)
9. [实验标定流程（详细步骤）](#九实验标定流程详细步骤)
10. [多方案对比](#十多方案对比)
11. [导出功能](#十一导出功能)
12. [常见问题](#十二常见问题)
13. [物理背景与局限](#十三物理背景与局限)

---

# 一、快速开始

1. **看默认结构**：程序启动时已加载 3 层示例结构
2. **拖动滑块**：主区域中间有"Axial position x (mm)"滑块，拖动可查看不同位置
3. **看六个指标**：主区域顶部有 EA/EI/Kp + Fu/My/Fc 六个指标
4. **改参数**：侧边栏展开任意层修改数值
5. **保存方案**：改好后在"💾 方案管理"保存

---

# 二、界面总览

## 主区域（从上到下）

| 区块 | 内容 |
|---|---|
| 单位约定 | 全局单位说明 |
| 使用说明书 | 可展开 |
| 轴向位置滑块 | 选择截面位置 |
| 第一部分：刚度分析 | 3 指标 + 3 曲线 + 力-位移曲线 + 方案对比 + 截面图 + 贡献图 |
| 第二部分：强度分析 | 4 指标 + 3 曲线 + 3 候选层表 |
| 参数明细表 | 当前截面所有层参数 |
| 导出功能 | 3 个导出按钮 |

## 侧边栏（从上到下）

| 区块 | 内容 |
|---|---|
| 导管总长度 | 全局设置 |
| 添加新层 | 插入新层 |
| 编辑各层 | 每层可展开 |
| 刚度修正系数 | EA、Kp |
| 抗压扁非线性参数 | 软化系数 c |
| 抗拉强度参数 | 粘接系数 η |
| 三点弯曲试验参数 | 跨距 L |
| 方案管理 | 保存/载入/删除 |
| 操作按钮 | 强制刷新、恢复示例 |

---

# 三、输入参数详解

## 3.1 普通材料层

| 参数 | 单位 | 说明 |
|---|---|---|
| 起始/结束位置 | mm | 轴向分段 |
| 内半径/外半径 | mm | 径向范围，内半径必须小于外半径 |
| 弹性模量 | MPa | 材料杨氏模量 E |
| 抗拉强度 | MPa | 材料极限抗拉强度 σ_uts |

## 3.2 编织层

| 参数 | 单位 | 说明 |
|---|---|---|
| 起始/结束位置 | mm | 轴向分段 |
| 内半径/外半径 | mm | 径向范围 |
| 扁丝宽度/厚度 | mm | 单根扁丝的尺寸 |
| 股数 | — | 每个方向的丝束数 |
| 每束根数 | — | 每束里并排的扁丝数 |
| 每英寸交叉数 PPI | 1/in | 编织密度 |
| 丝材模量 | MPa | 单根丝材弹性模量 |
| 丝材抗拉强度 | MPa | 单根丝材抗拉强度 |
| 原始基体体积分数 | — | 渗入热熔前已有基体占比（通常 0） |

## 3.3 弹簧圈

| 参数 | 单位 | 说明 |
|---|---|---|
| 起始/结束位置 | mm | 轴向分段 |
| 内半径/外半径 | mm | 径向范围 |
| 丝径 | mm | 单根丝直径 |
| 螺距 | mm | 相邻两圈的距离 |
| 丝材模量 | MPa | 丝材弹性模量 |
| 丝材抗拉强度 | MPa | 丝材抗拉强度 |
| 原始基体体积分数 | — | 通常 0 |

---

# 四、材料库使用

每层编辑区顶部有"📚 材料库"下拉菜单：

1. **选择材料**
2. **选择应用范围**：全部段 或 指定段
3. **点击"填入"**

## 普通材料库

| 材料 | E (MPa) | σ_uts (MPa) |
|---|---|---|
| PTFE (块体) | 500 | 106.2 |
| PTFE (挤出管) | 200 | 80.5 |
| Pebax 2533 | 12 | 15 |
| Pebax 3533 | 20 | 20 |
| Pebax 5533 | 30 | 25 |
| Pebax 6333 | 40 | 28 |
| Pebax 7233 | 50 | 30 |
| 尼龙 12 | 1500 | 45 |
| 尼龙 6 | 2500 | 70 |
| 聚氨酯 | 30 | 30 |
| 聚乙烯 (HDPE) | 900 | 25 |

## 丝材库

| 材料 | E_f (MPa) | σ_f (MPa) |
|---|---|---|
| 不锈钢 304 (冷加工) | 193000 | 2200 |
| 不锈钢 316LVM (冷加工) | 193000 | 2400 |
| 镍钛合金 (超弹) | 60000 | 1200 |
| 钴铬合金 (L605) | 220000 | 2500 |
| 铂钨合金 | 170000 | 800 |

---

# 五、刚度分析

## 三个刚度指标

| 指标 | 单位 | 物理意义 |
|---|---|---|
| **EA** | N | 拉长 100% 需要的力 |
| **EI** | N·mm² | 弯成单位曲率需要的弯矩 |
| **Kp** | N/mm | 直径减小 1 mm 需要的力 |

## 沿长度曲线

三张曲线分别显示 EA、EI、Kp 沿导管长度分布。

- 横轴：轴向位置（mm）
- 纵轴：对应刚度值
- 灰色竖虚线：当前滑块位置
- 台阶：结构变化

## 截面图

- 斜线填充：编织层
- 叉线填充：弹簧圈
- 点线填充：热熔自动填充层
- 纯色：普通材料

## 贡献条形图

显示每层对 EA、EI、Kp 的贡献百分比。找出"主力层"。

## 壁厚比提示

| 颜色 | 条件 | 含义 |
|---|---|---|
| 蓝框 | t/R < 0.1 | 薄壁，Kp 可信 |
| 黄框 | 0.1 ≤ t/R < 0.5 | 厚壁，Kp 有 10~40% 偏差 |
| 红框 | t/R ≥ 0.5 | 极厚壁，需实验标定 |

---

# 六、强度分析

## 三个强度指标

| 指标 | 单位 | 物理意义 |
|---|---|---|
| **Fu** | N | 拉断/拉屈服力 |
| **My** | N·mm | 弯曲屈服力矩 |
| **Fc** | N | 压扁起始屈服力 |

## 弯曲屈服控制层

各层曲率相同，表面应力与 E_z 和 r_out 相关。逐层计算该层表面达到抗拉强度时所需的整体弯矩，取最小值对应层为控制层。

## 压扁屈服控制层

各层应变相同。逐层计算该层的屈服应变（抗拉强度除以环向模量），取最小值对应层为控制层。

弹簧圈通常 E_θ 极高但抗拉强度相对有限，所以屈服应变最小，是压扁屈服的控制器。

## 轴向拉力分解

弹簧圈/编织层的 Fu 由两部分组成：

- **Fu_fiber**：丝材/弹簧贡献
- **Fu_matrix**：热熔填充贡献（含粘接系数 η 折减）

弹簧圈层的热熔填充贡献往往大于弹簧丝本身。

---

# 七、非线性力-位移曲线

## 模型

抗压扁力随变形增大而逐渐软化：

F(ΔD) = Kp · ΔD / (1 + c · ΔD / D)

其中 Kp 为初始线性刚度，D 为外径，c 为软化系数。

## 软化系数 c

| c 值 | 行为 | 适用场景 |
|---|---|---|
| 0 | 完全线性 | 仅供对比 |
| 0.5 | 轻微软化 | 厚壁、刚性导管 |
| 1.0 | 中等软化 | 默认，大多数微导管 |
| 2.0 | 明显软化 | 薄壁、柔性导管 |
| 3.0 | 强软化 | 极易压溃 |

## 曲线图解读

- 灰色虚线：线弹性外推
- 红色实线：当前方案非线性
- 其他颜色虚线：已保存方案
- 蓝/绿圆点：ΔD = 1mm、2mm 处的力值
- 灰竖点线：完全压扁位置
- 绿阴影：外径 10% 内的小变形线性区

---

# 八、修正系数详解

## 修正系数一览

| 系数 | 作用 | 默认值 | 影响范围 |
|---|---|---|---|
| EA 修正 | 修正轴向刚度理论值 | 1.0 | EA 绝对值 |
| Kp 修正 | 修正抗压扁刚度理论值 | 1.0 | Kp 绝对值 |
| 粘接系数 η | 修正热熔填充拉力贡献 | 0.8 | Fu 绝对值 |
| 软化系数 c | 控制力-位移曲线弯曲程度 | 1.0 | 曲线形状 |
| 跨距 L | 三点弯曲实验支点距离 | 30 mm | My 转 Fy |

## 为什么需要修正

理论模型存在以下理想化假设：

1. **材料线弹性**：实际聚合物在大变形下会屈服
2. **完全粘接**：实际层间可能有滑移
3. **圆环截面**：实际压扁时截面椭圆化
4. **平面截面**：实际有剪切变形
5. **材料均匀**：极薄管的有效模量低于块体

结果：理论值通常比实测值高 2~3 倍，需要通过修正系数折减。

## 修正系数不能直接测量

修正系数本身不能直接测量，它们是从**可测的实验曲线**反推出来的。标定流程见下一节。

---

# 九、实验标定流程（详细步骤）

## 9.1 准备工作

**设备**：
- 万能材料试验机（Instron、Zwick 等），量程 5~50 N
- 拉伸夹具（不能压扁导管）
- 平板压缩夹具（两块平行硬质平板）
- 三点弯曲夹具（两个支撑点 + 一个加载头）
- 游标卡尺或光学测量仪

**样品**：
- 至少 3 根同批次导管

## 9.2 拉伸实验（标定 EA 修正 + 粘接系数 η）

### 实验步骤

1. **取样**：取一段导管，长度 L₀ = 100 mm（或 50~200 mm 之间任意值）
2. **夹持**：两端插入金属芯轴，用锥形夹头夹住，避免压扁管腔
3. **加载**：以 1 mm/min 的恒定速度拉伸
4. **记录**：力 F 和位移 δ 的完整曲线，直到拉断或拉长 10%
5. **重复**：至少测 3 根，取平均

### 数据处理

**第一步：算实测 EA**

取曲线初始线性段（通常在前 1~5% 应变），斜率 k = ΔF/Δδ。

EA_实测 = k × L₀

例如：L₀ = 100 mm，斜率 k = 0.28 N/mm，则 EA_实测 = 28 N。

**第二步：算 EA 修正系数**

在工具中输入和实验样品相同的参数，得到 EA_理论。

EA 修正系数 = EA_实测 / EA_理论

例如：EA_实测 = 28 N，EA_理论 = 45 N，则 EA 修正系数 = 0.62。

**第三步：算粘接系数 η**

看曲线的断裂点或最高点，得到 Fu_实测。

在工具中把 η 暂时设为 1.0，得到 Fu_理论(η=1)。

先记录两件事：
- Fu_不含热熔：所有层 Fu_fiber 之和（不含 Fu_matrix）
- Fu_理论(η=1)：把 η 设为 1.0 时的总 Fu

则：

η = (Fu_实测 - Fu_不含热熔) / (Fu_理论(η=1) - Fu_不含热熔)

例如：Fu_实测 = 10.5 N，Fu_不含热熔 = 8.0 N，Fu_理论(η=1) = 13.0 N，则 η = (10.5 - 8.0) / (13.0 - 8.0) = 0.5。

**简化做法**：如果不方便算 Fu_不含热熔，直接看 Fu_实测 和 Fu_理论(η=1) 的比值，然后调 η 让工具算出的 Fu 和实测对齐即可。

## 9.3 平板压缩实验（标定 Kp 修正 + 软化系数 c）

### 实验步骤

1. **取样**：取一段短导管，长度 5~10 mm（太长会弯曲，不是纯压扁）
2. **放置**：水平放在两块平行平板之间
3. **加载**：上平板以恒定速度下压（如 1 mm/min）
4. **记录**：力 F 和位移 δ（即直径减小量 ΔD）的完整曲线，直到直径减小 50% 或压溃
5. **重复**：至少测 3 根，取平均

**注意**：
- 试样要短（5~10 mm），避免梁效应
- 平板要平行、光滑
- 记录的是位移（直径减小量），不是应变

### 数据处理

**第一步：算实测 Kp**

取曲线初始线性段（通常在前 5~10% 外径变化），斜率 k = ΔF/ΔD。

Kp_实测 = k

例如：斜率 k = 3.2 N/mm，则 Kp_实测 = 3.2 N/mm。

**第二步：算 Kp 修正系数**

在工具中输入和实验样品相同的参数，得到 Kp_理论。

Kp 修正系数 = Kp_实测 / Kp_理论

例如：Kp_实测 = 3.2 N/mm，Kp_理论 = 8.0 N/mm，则 Kp 修正系数 = 0.40。

**第三步：算软化系数 c**

从实测曲线上取两个点（避开初始线性段），例如：

- 点 A：ΔD = 0.5 mm，F = F_A = 2.0 N
- 点 B：ΔD = 1.0 mm，F = F_B = 3.5 N

代入非线性模型 F(ΔD) = Kp · ΔD / (1 + c · ΔD / D)，两式相除消掉 Kp：

F_A / F_B = [0.5 / (1 + c · 0.5 / D)] / [1.0 / (1 + c · 1.0 / D)]

整理得：

c = 2D(r - 0.5) / (1 - r)

其中 r = F_A / F_B，D 是导管外径。

例如：D = 0.8 mm，r = 2.0 / 3.5 = 0.571，则：

c = 2 × 0.8 × (0.571 - 0.5) / (1 - 0.571) = 0.265

**验证**：把 Kp 修正和 c 填进工具，看理论曲线是否和实测曲线重合。如果不重合，调整取点位置重新计算。

## 9.4 三点弯曲跨距 L

直接用卡尺量三点弯曲夹具两个支点之间的距离。填进侧边栏。

例如：两个支撑点间距 30 mm，则 L = 30 mm。

## 9.5 完整标定示例

**实验数据**（假设某微导管）：

| 项目 | 数值 |
|---|---|
| 拉伸长度 L₀ | 100 mm |
| 拉伸初始斜率 k | 0.28 N/mm |
| 拉伸断裂力 Fu_实测 | 10.5 N |
| 压缩外径 D | 0.8 mm |
| 压缩初始斜率 | 3.2 N/mm |
| 压缩 ΔD=0.5mm 时 F | 2.0 N |
| 压缩 ΔD=1.0mm 时 F | 3.5 N |
| 三点弯曲跨距 L | 30 mm |

**标定结果**：

| 系数 | 计算过程 | 数值 |
|---|---|---|
| EA 修正 | 28 / 45 | **0.62** |
| Kp 修正 | 3.2 / 8.0 | **0.40** |
| 软化系数 c | 2×0.8×(0.571-0.5)/(1-0.571) | **0.27** |
| 粘接系数 η | (10.5-8.0)/(13.0-8.0) | **0.50** |
| 跨距 L | 卡尺测量 | **30 mm** |

把这 5 个数填进侧边栏。

## 9.6 没有万能试验机时的替代方案

**拉伸替代**：
- 把导管竖直悬挂，下端挂已知重量的砝码
- 用游标卡尺测量伸长量
- EA_实测 = mg · L₀ / ΔL

**压缩替代**：
- 把导管放在游标卡尺的两个量爪之间
- 用弹簧测力计缓慢加压
- 记录力与管径变化

**精度差一些，但趋势可用**。

## 9.7 标定后的使用

1. **同类结构复用**：结构相近（层序相同、材料相近）的导管可以共用同一套系数
2. **结构变化较大时重新标定**：例如编织密度差 3 倍以上
3. **定期复测**：材料批次更换后建议重新标定

## 9.8 如果不能做实验

使用**保守默认值**：

| 系数 | 保守值 |
|---|---|
| EA 修正 | 0.6 |
| Kp 修正 | 0.4 |
| 粘接系数 η | 0.8 |
| 软化系数 c | 1.0 |
| 跨距 L | 30 mm |

**此时工具的作用**：
- 对比不同设计方案的相对优劣
- 找趋势、找拐点、找最优点
- 早期发现设计缺陷

**不能做**：报绝对数值。

---

# 十、多方案对比

## 使用流程

1. 配置好一个方案，输入方案名称
2. 点击"保存当前方案"
3. 修改参数或切换结构，保存第二个方案
4. 主区域曲线图自动叠加显示所有方案

## 图例解读

每个图例包含方案名 + 关键参数：

- Current (Kp_corr=X.XX, c=X.XX)
- 方案名 (Kp_corr=X.XX, c=X.XX)

力-位移曲线的图例额外显示 Kp 值。

## 关键机制：快照

保存方案时，程序会冻结当时的结构、修正系数、粘接系数、软化系数、跨距。保存后修改这些参数不会同步到已保存方案。

## 方案对比表

主区域下方有"📊 方案对比（当前截面）"表格，显示所有方案在当前 x 位置的六项指标。

---

# 十一、导出功能

| 按钮 | 内容 | 格式 |
|---|---|---|
| 当前截面参数表 | 当前 x 位置所有层参数 | CSV |
| 沿长度曲线数据 | 200 个采样点的六条曲线 | CSV |
| 完整报告 | 多 sheet 完整报告 | Excel |

Excel 报告的 sheet：概览、当前截面指标、力-位移曲线、当前截面参数、沿长度曲线、方案对比、各层原始数据。

CSV 用 UTF-8 with BOM 编码，Excel 直接打开不会乱码。

---

# 十二、常见问题

**Q1：算出来 Kp 太大，感觉不现实？**
A：Kp 是线性小变形刚度，真实值需乘修正系数 0.3~0.5。

**Q2：为什么改了模量，Fu 没变？**
A：Fu 只取决于抗拉强度，与弹性模量无关。

**Q3：为什么弹簧圈层 Fu 有多个分量？**
A：弹簧圈层 Fu = 弹簧丝贡献 + 热熔填充贡献。后者往往更大。

**Q4：为什么弯曲屈服不是最外层控制？**
A：控制层由轴向模量、外半径、抗拉强度三者共同决定。

**Q5：为什么弹簧圈是压扁屈服控制层？**
A：弹簧圈屈服应变（抗拉强度除以环向模量）最小。

**Q5b：修正系数怎么标定？**
A：见第九节，从拉伸和压缩实验反推。

**Q6：c 应该填多少？**
A：没有实验时默认 1.0。做过实验后，调 c 让曲线形状与实测接近。

**Q7：为什么多条曲线颜色看不清？**
A：方案数多时建议只保留 3~5 个对比。

**Q8：为什么 Scheme 的 Kp 和 Current 差很多？**
A：方案是快照，保存时的参数可能和现在不同。看图例里的 Kp_corr 和 c 值。

**Q9：改了参数图表没更新？**
A：按一次 Enter，或点"🔄 强制刷新计算"。

**Q10：Excel 导出报错？**
A：需要安装 openpyxl：pip install openpyxl。

---

# 十三、物理背景与局限

## 理论模型

- 多层同心圆管，各层完全粘接
- 材料线弹性（非线性通过修正系数补偿）
- 小变形假设（大变形通过软化系数补偿）
- Timoshenko 薄环理论用于抗压扁（厚壁用厚环修正）

## 主要简化

| 简化 | 影响 |
|---|---|
| 材料线弹性 | 大变形下高估刚度 |
| 完全粘接 | 忽略层间滑移 |
| 圆环截面 | 忽略椭圆化 |
| 平面截面 | 忽略剪切变形 |

## 适用范围

| 场景 | 是否适用 |
|---|---|
| 相对比较多个设计方案 | 完全适用 |
| 参数扫描找最优点 | 完全适用 |
| 早期发现设计缺陷 | 完全适用 |
| 预测绝对刚度值 | 需实验标定 |
| 报规格书 | 需实验 |
| 预测扭结精确位置 | 需有限元 |
| 疲劳寿命 | 需疲劳实验 |
| 长期蠕变 | 需粘弹性模型 |

## 工具定位

本工具是**设计筛选工具**，不是实验替代品。

- 作用：在 5 分钟内扫 100 种结构组合，找出最有希望的几种
- 不作用：替代实验、报规格书、精确预测失效

使用建议：先做一次标定实验（半天），得到修正系数后，工具就可以用于同类导管的快速预测。
    """)

# ============================================================
# 主区域剩余部分
# ============================================================

structure = st.session_state.structure
L_total = st.session_state.L_total
ea_correction = st.session_state.ea_correction
kp_correction = st.session_state.kp_correction
L_span = st.session_state.span_L
eta_bond = st.session_state.eta_bond
softening_c = st.session_state.softening_c
saved_schemes = st.session_state.saved_schemes

x_pos_safe = min(max(st.session_state.x_pos, 0.0), L_total)
x_pos = st.slider("Axial position x (mm)", min_value=0.0, max_value=L_total,
                  value=x_pos_safe, step=0.5)
st.session_state.x_pos = x_pos

all_schemes = []

xs, EA_arr, EI_arr, Kp_arr, Fu_arr, My_arr, Fc_arr = compute_along_length(
    structure, L_total, ea_correction, kp_correction, eta_bond)
all_schemes.append({
    'name': 'Current',
    'xs': xs,
    'EA': EA_arr, 'EI': EI_arr, 'Kp': Kp_arr,
    'Fu': Fu_arr, 'My': My_arr, 'Fc': Fc_arr,
    'is_current': True,
    'params': {
        'name': 'Current',
        'structure': structure,
        'L_total': L_total,
        'ea_correction': ea_correction,
        'kp_correction': kp_correction,
        'eta_bond': eta_bond,
        'softening_c': softening_c,
        'span_L': L_span,
    }
})

for s in saved_schemes:
    try:
        s_xs, s_EA, s_EI, s_Kp, s_Fu, s_My, s_Fc = compute_along_length(
            s['structure'], s['L_total'],
            s['ea_correction'], s['kp_correction'], s['eta_bond'])
        all_schemes.append({
            'name': s['name'],
            'xs': s_xs,
            'EA': s_EA, 'EI': s_EI, 'Kp': s_Kp,
            'Fu': s_Fu, 'My': s_My, 'Fc': s_Fc,
            'is_current': False,
            'params': s,
        })
    except Exception as e:
        st.warning(f"方案 '{s['name']}' 计算失败：{e}")

scheme_colors = plt.cm.tab10(np.linspace(0, 1, max(len(all_schemes), 1)))

layers = compute_at_x(structure, x_pos, eta_bond=eta_bond)

def make_label(sch):
    p = sch['params']
    kp_c = p['kp_correction']
    c_v = p['softening_c']
    if sch['is_current']:
        return f"Current (Kp_corr={kp_c:.2f}, c={c_v:.2f})"
    else:
        return f"{sch['name']} (Kp_corr={kp_c:.2f}, c={c_v:.2f})"

# ============================================================
# 第一部分：刚度分析
# ============================================================
st.markdown("## 一、Stiffness Analysis（刚度分析）")
st.caption("刚度描述导管抵抗变形的能力。单位：EA (N)、EI (N·mm²)、Kp (N/mm)。")

if not layers:
    st.warning("该位置没有层存在。")
else:
    EA, EI, Kp, EA_c, EI_c, Kp_c, model_used, thick_ratio = compute_stiffness(layers, ea_correction, kp_correction)

    c1, c2, c3 = st.columns(3)
    c1.metric("Axial Stiffness EA (N)", f"{EA:.2f}")
    c2.metric("Bending Stiffness EI (N·mm²)", f"{EI:.2f}")
    c3.metric("Crush Stiffness Kp (N/mm)", f"{Kp:.2f}")

    st.subheader("Stiffness along Length")
    if len(all_schemes) > 1:
        st.caption(f"当前方案 + {len(all_schemes)-1} 个已保存方案叠加显示。")
    fig_s, axes_s = plt.subplots(3, 1, figsize=(10, 12))
    fig_s.suptitle("Stiffness Distribution along Catheter Length", y=0.98, fontsize=13)

    for si, sch in enumerate(all_schemes):
        color = scheme_colors[si]
        lw = 2.5 if sch['is_current'] else 1.5
        ls = '-' if sch['is_current'] else '--'
        label_s = make_label(sch)

        axes_s[0].plot(sch['xs'], sch['EA'], color=color, linewidth=lw, linestyle=ls, label=label_s)
        axes_s[1].plot(sch['xs'], sch['EI'], color=color, linewidth=lw, linestyle=ls, label=label_s)
        axes_s[2].plot(sch['xs'], sch['Kp'], color=color, linewidth=lw, linestyle=ls, label=label_s)

    axes_s[0].set_ylabel('EA (N)')
    axes_s[0].set_xlabel('Axial position (mm)')
    axes_s[0].set_title('Axial Stiffness')
    axes_s[0].grid(True); axes_s[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[0].legend(loc='best', fontsize=8)

    axes_s[1].set_ylabel('EI (N·mm²)')
    axes_s[1].set_xlabel('Axial position (mm)')
    axes_s[1].set_title('Bending Stiffness')
    axes_s[1].grid(True); axes_s[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[1].legend(loc='best', fontsize=8)

    axes_s[2].set_ylabel('Kp (N/mm)')
    axes_s[2].set_xlabel('Axial position (mm)')
    axes_s[2].set_title(f'Crush Stiffness (current correction × {kp_correction:.3f})')
    axes_s[2].grid(True); axes_s[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[2].legend(loc='best', fontsize=8)

    fig_s.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_s)

    # 非线性力-位移曲线
    st.subheader("Crush Force–Displacement Curve (Non-linear)")
    st.caption(
        f"Current section Kp = {Kp:.3f} N/mm (with correction factor {kp_correction:.3f}). "
        f"Softening coefficient c = {softening_c:.2f}. "
        f"Non-linear model: F = Kp·ΔD / (1 + c·ΔD/D)."
    )

    r_outer_max = max(l['r_out'] for l in layers)
    D_outer = 2 * r_outer_max

    dD_max = 2.0
    dD_range = np.linspace(0, dD_max, 300)
    F_linear = Kp * dD_range
    F_nonlinear = compute_crush_force_nonlinear(Kp, D_outer, dD_range, softening_c)

    fig_cd, ax_cd = plt.subplots(figsize=(10, 6))

    for si, sch in enumerate(all_schemes):
        if sch['is_current']:
            continue
        try:
            s_params = sch['params']
            s_layers = compute_at_x(s_params['structure'], x_pos,
                                    eta_bond=s_params['eta_bond'])
            if s_layers:
                _, _, s_Kp_val, _, _, _, _, _ = compute_stiffness(
                    s_layers, s_params['ea_correction'], s_params['kp_correction'])
                s_D_outer = 2 * max(l['r_out'] for l in s_layers)
                s_c = s_params['softening_c']
                s_F_nl = compute_crush_force_nonlinear(
                    s_Kp_val, s_D_outer, dD_range, s_c)
                label_s = f"{sch['name']} (Kp={s_Kp_val:.2f} N/mm, c={s_c:.2f})"
                ax_cd.plot(dD_range, s_F_nl, color=scheme_colors[si],
                           linewidth=1.5, linestyle='--', label=label_s)
        except Exception:
            pass

    label_lin = f"Current: Linear (Kp={Kp:.2f} N/mm)"
    label_nl = f"Current: Non-linear (Kp={Kp:.2f} N/mm, c={softening_c:.2f})"
    ax_cd.plot(dD_range, F_linear, '--', color='gray', linewidth=1.8, label=label_lin)
    ax_cd.plot(dD_range, F_nonlinear, 'r-', linewidth=2.5, label=label_nl)

    for dD_mark, color in [(1.0, 'blue'), (2.0, 'darkgreen')]:
        if dD_mark <= dD_max:
            F_lin_mark = Kp * dD_mark
            F_nl_mark = compute_crush_force_nonlinear(Kp, D_outer, dD_mark, softening_c)

            ax_cd.plot(dD_mark, F_nl_mark, marker='o', markersize=11, color=color,
                       markeredgecolor='white', markeredgewidth=1.5, zorder=5)
            ax_cd.plot(dD_mark, F_lin_mark, marker='o', markersize=8, color=color,
                       markerfacecolor='white', markeredgewidth=1.5, zorder=4)

            delta_pct = (F_lin_mark - F_nl_mark) / F_lin_mark * 100 if F_lin_mark > 0 else 0
            ax_cd.annotate(
                f'ΔD = {dD_mark:.1f} mm\n'
                f'F (NL) = {F_nl_mark:.3f} N\n'
                f'F (linear) = {F_lin_mark:.3f} N\n'
                f'Softening: -{delta_pct:.1f}%',
                xy=(dD_mark, F_nl_mark),
                xytext=(dD_mark + 0.15, F_nl_mark + 0.05 * max(F_linear)),
                fontsize=9.5,
                color=color,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor=color, alpha=0.95),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.2)
            )

    if D_outer <= dD_max:
        ax_cd.axvline(x=D_outer, color='gray', linestyle=':', alpha=0.7,
                      label=f'Full collapse (ΔD = D = {D_outer:.3f} mm)')

    dD_10 = 0.1 * D_outer
    if dD_10 < dD_max:
        ax_cd.axvspan(0, dD_10, alpha=0.08, color='green')
        ax_cd.text(dD_10 / 2, max(F_linear) * 0.05,
                   'Small deformation\n(linear region)',
                   ha='center', fontsize=9, color='green')

    ax_cd.set_xlabel('Diameter reduction ΔD (mm)')
    ax_cd.set_ylabel('Radial force F (N)')
    ax_cd.set_title('Crush Force–Displacement Curve (Non-linear Model)')
    ax_cd.grid(True, linestyle='--', alpha=0.6)
    ax_cd.legend(loc='upper left', fontsize=8)
    ax_cd.set_xlim(0, dD_max)

    y_max = max(max(F_linear), max(F_nonlinear)) * 1.15
    ax_cd.set_ylim(0, y_max)

    fig_cd.tight_layout()
    st.pyplot(fig_cd)

    st.markdown("**关键变形量下的力值对比（当前方案）**")
    table_rows = []
    for dD_v in [0.1, 0.2, 0.5, 1.0, 1.5, 2.0]:
        F_lin = Kp * dD_v
        F_nl = compute_crush_force_nonlinear(Kp, D_outer, dD_v, softening_c)
        delta_pct = (F_lin - F_nl) / F_lin * 100 if F_lin > 0 else 0
        table_rows.append({
            'ΔD (mm)': f"{dD_v:.1f}",
            'ΔD / Outer D': f"{dD_v / D_outer * 100:.1f}%" if D_outer > 0 else "—",
            'Linear F (N)': f"{F_lin:.4f}",
            'Non-linear F (N)': f"{F_nl:.4f}",
            'Softening': f"-{delta_pct:.1f}%"
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    if len(all_schemes) > 1:
        st.markdown("---")
        st.subheader("📊 方案对比（当前截面）")
        st.caption(f"x = {x_pos:.1f} mm 处所有方案的六项指标对比，含关键参数")

        compare_rows = []
        for sch in all_schemes:
            p = sch['params']
            try:
                if sch['is_current']:
                    s_layers_cmp = layers
                else:
                    s_layers_cmp = compute_at_x(p['structure'], x_pos,
                                                eta_bond=p['eta_bond'])
                if s_layers_cmp:
                    s_EA_x, s_EI_x, s_Kp_x, _, _, _, _, _ = compute_stiffness(
                        s_layers_cmp, p['ea_correction'], p['kp_correction'])
                    s_Fu_x, _ = compute_axial_strength(s_layers_cmp)
                    s_My_x, _, _ = compute_bending_yield(s_layers_cmp)
                    s_Fc_x, _, _ = compute_collapse_force(s_layers_cmp)
                    scheme_label = sch['name'] + (' (current)' if sch['is_current'] else '')
                    compare_rows.append({
                        'Scheme': scheme_label,
                        'Kp_corr': f"{p['kp_correction']:.2f}",
                        'c': f"{p['softening_c']:.2f}",
                        'η': f"{p['eta_bond']:.2f}",
                        'EA (N)': f"{s_EA_x:.2f}",
                        'EI (N·mm²)': f"{s_EI_x:.2f}",
                        'Kp (N/mm)': f"{s_Kp_x:.2f}",
                        'Fu (N)': f"{s_Fu_x:.2f}",
                        'My (N·mm)': f"{s_My_x:.4f}",
                        'Fc (N)': f"{s_Fc_x:.2f}"
                    })
            except Exception:
                pass
        st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

    st.info(
        f"**模型说明**：非线性模型 F = Kp·ΔD / (1 + c·ΔD/D) 中，"
        f"c 越大曲线越向下弯曲。当前 c = {softening_c:.2f}。"
        f"标定方法见说明书第九节。"
    )

    st.subheader("Cross-section View")
    fig_c, ax_c = plt.subplots(figsize=(5, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(layers), 1)))
    for i, l in enumerate(layers):
        r_in, r_out = l['r_in'], l['r_out']
        ax_c.add_patch(plt.Circle((0, 0), r_out, color=colors[i], alpha=0.6))
        ax_c.add_patch(plt.Circle((0, 0), r_in, color='white', fill=True))
        if l['type'] == '编织层':
            ax_c.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360, width=r_out - r_in,
                                          fill=False, hatch='///', edgecolor='none'))
        elif l['type'] == '弹簧圈':
            ax_c.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360, width=r_out - r_in,
                                          fill=False, hatch='xxx', edgecolor='none'))
        elif l.get('is_filler', False):
            ax_c.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360, width=r_out - r_in,
                                          fill=False, hatch='...', edgecolor='none'))
    inner_r = min(l['r_in'] for l in layers)
    if inner_r > 0:
        ax_c.add_patch(plt.Circle((0, 0), inner_r, color='white', fill=True))
    R_max = max(l['r_out'] for l in layers)
    ax_c.set_xlim(-R_max*1.2, R_max*1.2); ax_c.set_ylim(-R_max*1.2, R_max*1.2)
    ax_c.set_aspect('equal'); ax_c.axis('off')
    st.pyplot(fig_c)

    st.subheader("Layer Contributions to Stiffness")
    labels = [l['name'] for l in layers]
    ea_pct = [v/EA*100 if EA > 0 else 0 for v in EA_c]
    ei_pct = [v/EI*100 if EI > 0 else 0 for v in EI_c]
    kp_pct = [v/Kp*100 if Kp > 0 else 0 for v in Kp_c]

    fig_cb, axes_cb = plt.subplots(1, 3, figsize=(15, 4))
    fig_cb.suptitle("Layer Contributions to Stiffness (%)", y=1.02, fontsize=13)

    axes_cb[0].bar(labels, ea_pct, color=colors)
    axes_cb[0].set_title('Axial (EA)')
    axes_cb[0].set_ylabel('Contribution (%)')
    axes_cb[0].grid(axis='y', linestyle='--', alpha=0.6)

    axes_cb[1].bar(labels, ei_pct, color=colors)
    axes_cb[1].set_title('Bending (EI)')
    axes_cb[1].set_ylabel('Contribution (%)')
    axes_cb[1].grid(axis='y', linestyle='--', alpha=0.6)

    axes_cb[2].bar(labels, kp_pct, color=colors)
    axes_cb[2].set_title(f'Crush (Kp) - {model_used}')
    axes_cb[2].set_ylabel('Contribution (%)')
    axes_cb[2].grid(axis='y', linestyle='--', alpha=0.6)

    fig_cb.tight_layout(rect=[0, 0, 1, 0.95])
    st.pyplot(fig_cb)

    filler_names = [l['name'] for l in layers if l.get('is_filler', False)]
    if filler_names:
        st.info(f"当前段缺失的层已自动用热熔材料填充：{', '.join(filler_names)}。")

    if thick_ratio < 0.1:
        st.info(f"壁厚/半径比 = **{thick_ratio:.3f}** < 0.1（薄壁）。抗压扁模型：**{model_used}**。")
    elif thick_ratio < 0.5:
        st.warning(f"壁厚/半径比 = **{thick_ratio:.3f}** ∈ [0.1, 0.5)（厚壁）。抗压扁模型：**{model_used}**。")
    else:
        st.error(f"壁厚/半径比 = **{thick_ratio:.3f}** ≥ 0.5（极厚壁）。抗压扁模型：**{model_used}**。")

# ============================================================
# 第二部分：强度分析
# ============================================================
st.markdown("---")
st.markdown("## 二、Strength Analysis（强度分析）")
st.caption(f"强度描述导管能承受的极限载荷。弯曲按三点弯曲换算，跨距 L = {L_span:.1f} mm。粘接系数 η = {eta_bond:.2f}。")

if layers:
    Fu, Fu_layer = compute_axial_strength(layers)
    My, bending_ctrl, bending_cands = compute_bending_yield(layers)
    Fc, collapse_ctrl, collapse_cands = compute_collapse_force(layers)

    Fy_bending = 4 * My / L_span if L_span > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Axial Tensile Force Fu (N)", f"{Fu:.2f}")
    c2.metric("Bending Yield Moment My (N·mm)", f"{My:.4f}")
    c3.metric("Bending Yield Force (3-pt) (N)", f"{Fy_bending:.4f}",
              help=f"三点弯曲跨距 L = {L_span:.1f} mm")
    c4.metric("Collapse Force Fc (N)", f"{Fc:.2f}")

    st.info(f"**弯曲屈服控制层**：{bending_ctrl}。**压扁屈服控制层**：{collapse_ctrl}。")

    st.subheader("Strength along Length")
    if len(all_schemes) > 1:
        st.caption(f"当前方案 + {len(all_schemes)-1} 个已保存方案叠加显示。")
    fig_t, axes_t = plt.subplots(3, 1, figsize=(10, 12))
    fig_t.suptitle("Strength Distribution along Catheter Length", y=0.98, fontsize=13)

    for si, sch in enumerate(all_schemes):
        color = scheme_colors[si]
        lw = 2.5 if sch['is_current'] else 1.5
        ls = '-' if sch['is_current'] else '--'
        label_s = make_label(sch)

        axes_t[0].plot(sch['xs'], sch['Fu'], color=color, linewidth=lw, linestyle=ls, label=label_s)
        axes_t[1].plot(sch['xs'], sch['My'], color=color, linewidth=lw, linestyle=ls, label=label_s)
        axes_t[2].plot(sch['xs'], sch['Fc'], color=color, linewidth=lw, linestyle=ls, label=label_s)

    axes_t[0].set_ylabel('Fu (N)')
    axes_t[0].set_xlabel('Axial position (mm)')
    axes_t[0].set_title('Max Axial Tensile Force')
    axes_t[0].grid(True); axes_t[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[0].legend(loc='best', fontsize=8)

    axes_t[1].set_ylabel('My (N·mm)')
    axes_t[1].set_xlabel('Axial position (mm)')
    axes_t[1].set_title('Bending Yield Moment')
    axes_t[1].grid(True); axes_t[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[1].legend(loc='best', fontsize=8)

    axes_t[2].set_ylabel('Fc (N)')
    axes_t[2].set_xlabel('Axial position (mm)')
    axes_t[2].set_title('Collapse Force (weakest layer controls)')
    axes_t[2].grid(True); axes_t[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[2].legend(loc='best', fontsize=8)

    fig_t.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_t)

    st.subheader("Bending Yield — Candidate Layers")
    b_rows = []
    for c in bending_cands:
        M_i = c['M_y']
        F_i = 4 * M_i / L_span if L_span > 0 else 0.0
        b_rows.append({
            "Layer": c['layer'],
            "E_z (MPa)": f"{c['E_z']:.1f}",
            "r_out (mm)": f"{c['r_out']:.4f}",
            "σ_uts (MPa)": f"{c['sigma_uts']:.1f}",
            "M_y (N·mm)": f"{M_i:.4f}",
            f"Fy (N, L={L_span:.0f}mm)": f"{F_i:.4f}"
        })
    st.dataframe(pd.DataFrame(b_rows), use_container_width=True)

    st.subheader("Collapse — Candidate Layers")
    c_rows = []
    for c in collapse_cands:
        c_rows.append({
            "Layer": c['layer'],
            "E_theta (MPa)": f"{c['E_theta']:.1f}",
            "t (mm)": f"{c['t']:.4f}",
            "σ_uts (MPa)": f"{c['sigma_uts']:.1f}",
            "ε_y = σ/E": f"{c['sigma_uts']/c['E_theta']*100:.2f}%",
            "F_c (N)": f"{c['F_c']:.4f}"
        })
    st.dataframe(pd.DataFrame(c_rows), use_container_width=True)

    st.subheader("Axial Tensile — Layer Contributions")
    fu_rows = []
    for i, l in enumerate(layers):
        if l['type'] == '弹簧圈':
            method = "Spring + matrix"
        elif l['type'] == '编织层':
            method = "Fiber + matrix"
        elif l.get('is_filler', False):
            method = "Filler (σ·A)"
        else:
            method = "σ·A"
        fu_rows.append({
            "Layer": l['name'],
            "Type": l['type'],
            "Method": method,
            "UTS (MPa)": f"{l['sigma_uts']:.1f}",
            "Fu_fiber (N)": f"{l.get('Fu_fiber', 0.0):.4f}",
            "Fu_matrix (N)": f"{l.get('Fu_matrix', 0.0):.4f}",
            "Fu_total (N)": f"{Fu_layer[i]:.4f}"
        })
    st.dataframe(pd.DataFrame(fu_rows), use_container_width=True)

# ============================================================
# 参数明细表
# ============================================================
st.markdown("---")
st.subheader("Layer Parameters at This Position")
if layers:
    param_rows = []
    for l in layers:
        row = {
            "Layer": l['name'], "Type": l['type'],
            "r_in (mm)": f"{l['r_in']:.4f}", "r_out (mm)": f"{l['r_out']:.4f}",
            "E_z (MPa)": f"{l['E_z']:.2f}", "E_theta (MPa)": f"{l['E_theta']:.2f}",
            "UTS (MPa)": f"{l['sigma_uts']:.1f}"
        }
        row["V_f (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        row["V_void (%)"] = f"{l['V_void']*100:.2f}%" if l['V_void'] is not None else "—"
        param_rows.append(row)
    param_df = pd.DataFrame(param_rows)
    st.dataframe(param_df, use_container_width=True)
else:
    param_df = pd.DataFrame()

# ============================================================
# 导出功能
# ============================================================
st.markdown("---")
st.subheader("📥 导出结果")

exp_col1, exp_col2, exp_col3 = st.columns(3)

with exp_col1:
    if not param_df.empty:
        csv_bytes = param_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 当前截面参数表 (CSV)",
            data=csv_bytes,
            file_name=f"cross_section_x{x_pos:.1f}mm.csv",
            mime="text/csv",
            key="dl_param_csv"
        )
    else:
        st.button("📄 当前截面参数表 (CSV)", disabled=True, key="dl_param_csv_disabled")

with exp_col2:
    curve_df = pd.DataFrame({
        'x_mm': xs,
        'EA_N': EA_arr,
        'EI_N_mm2': EI_arr,
        'Kp_N_per_mm': Kp_arr,
        'Fu_N': Fu_arr,
        'My_N_mm': My_arr,
        'Fc_N': Fc_arr
    })
    curve_csv = curve_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📈 沿长度曲线数据 (CSV)",
        data=curve_csv,
        file_name="along_length_curves.csv",
        mime="text/csv",
        key="dl_curve_csv"
    )

with exp_col3:
    if HAS_OPENPYXL:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            overview_data = {
                '参数': ['导管总长度 (mm)', '当前轴向位置 (mm)', 'EA 修正系数',
                         'Kp 修正系数', '粘接系数 η', '三点弯曲跨距 (mm)', '软化系数 c',
                         '已保存方案数'],
                '值': [L_total, x_pos, ea_correction, kp_correction, eta_bond, L_span, softening_c,
                       len(saved_schemes)]
            }
            pd.DataFrame(overview_data).to_excel(writer, sheet_name='概览', index=False)

            if layers:
                cur_metrics = {
                    '指标': ['EA (N)', 'EI (N·mm²)', 'Kp (N/mm)', 'Fu (N)', 'My (N·mm)', 'Fc (N)'],
                    '值': [EA, EI, Kp, Fu, My, Fc]
                }
                pd.DataFrame(cur_metrics).to_excel(writer, sheet_name='当前截面指标', index=False)

                dD_export = np.linspace(0, 2.0, 200)
                F_lin_export = Kp * dD_export
                F_nl_export = compute_crush_force_nonlinear(Kp, D_outer, dD_export, softening_c)
                fd_df = pd.DataFrame({
                    'DeltaD_mm': dD_export,
                    'F_linear_N': F_lin_export,
                    'F_nonlinear_N': F_nl_export
                })
                fd_df.to_excel(writer, sheet_name='力-位移曲线', index=False)

            if not param_df.empty:
                param_df.to_excel(writer, sheet_name='当前截面参数', index=False)

            curve_df.to_excel(writer, sheet_name='沿长度曲线', index=False)

            if len(all_schemes) > 1:
                compare_rows_export = []
                for sch in all_schemes:
                    p = sch['params']
                    try:
                        if sch['is_current']:
                            s_layers_export = layers
                        else:
                            s_layers_export = compute_at_x(p['structure'], x_pos,
                                                          eta_bond=p['eta_bond'])
                        if s_layers_export:
                            s_EA_x, s_EI_x, s_Kp_x, _, _, _, _, _ = compute_stiffness(
                                s_layers_export, p['ea_correction'], p['kp_correction'])
                            s_Fu_x, _ = compute_axial_strength(s_layers_export)
                            s_My_x, _, _ = compute_bending_yield(s_layers_export)
                            s_Fc_x, _, _ = compute_collapse_force(s_layers_export)
                            compare_rows_export.append({
                                'Scheme': sch['name'] + (' (current)' if sch['is_current'] else ''),
                                'Kp_correction': p['kp_correction'],
                                'softening_c': p['softening_c'],
                                'eta_bond': p['eta_bond'],
                                'EA_N': s_EA_x,
                                'EI_N_mm2': s_EI_x,
                                'Kp_N_per_mm': s_Kp_x,
                                'Fu_N': s_Fu_x,
                                'My_N_mm': s_My_x,
                                'Fc_N': s_Fc_x
                            })
                    except Exception:
                        pass
                if compare_rows_export:
                    pd.DataFrame(compare_rows_export).to_excel(
                        writer, sheet_name=f'方案对比_x{x_pos:.0f}mm', index=False)

            for i, layer in enumerate(structure):
                sheet_name = f'层{i+1}_{layer["name"]}'[:31]
                try:
                    layer['data'].to_excel(writer, sheet_name=sheet_name, index=False)
                except Exception:
                    pass
        buffer.seek(0)
        st.download_button(
            label="📊 完整报告 (Excel)",
            data=buffer.getvalue(),
            file_name="catheter_analysis_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_excel"
        )
    else:
        st.button("📊 完整报告 (需 openpyxl)", disabled=True, key="dl_excel_disabled")
        st.caption("安装: pip install openpyxl")

st.caption("CSV 用 UTF-8 with BOM 编码，Excel 打开不会乱码。")
