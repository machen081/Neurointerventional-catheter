import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io

# 尝试导入 openpyxl（Excel 导出需要）
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

st.set_page_config(page_title="微导管多层结构分析", layout="wide")

# ==================== 材料库 ====================
# 普通材料典型值（室温，25°C）
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

# 丝材典型值（用于编织层和弹簧圈的丝材）
MATERIAL_LIBRARY_WIRE = {
    "自定义": None,
    "不锈钢 304 (冷加工)": {"E_f": 193000.0, "sigma_f": 2200.0},
    "不锈钢 316LVM (冷加工)": {"E_f": 193000.0, "sigma_f": 2400.0},
    "镍钛合金 (超弹)": {"E_f": 60000.0, "sigma_f": 1200.0},
    "钴铬合金 (L605)": {"E_f": 220000.0, "sigma_f": 2500.0},
    "铂钨合金": {"E_f": 170000.0, "sigma_f": 800.0},
}

# 全局单位说明
UNIT_INFO = {
    "长度": "mm",
    "弹性模量": "MPa",
    "抗拉强度": "MPa",
    "力": "N",
    "刚度 EA": "N",
    "刚度 EI": "N·mm²",
    "刚度 Kp": "N/mm",
    "力矩 My": "N·mm",
}

# ==================== 层类型定义 ====================
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
CURRENT_VERSION = "v17_units_library_export"

if 'structure_version' not in st.session_state or st.session_state.structure_version != CURRENT_VERSION:
    st.session_state.structure = create_default_structure()
    st.session_state.structure_version = CURRENT_VERSION
    st.session_state.L_total = 30.0
    st.session_state.x_pos = 0.0
    st.session_state.ea_correction = 1.0
    st.session_state.kp_correction = 1.0
    st.session_state.span_L = 30.0
    st.session_state.eta_bond = 0.8
else:
    st.session_state.structure = normalize_structure(st.session_state.structure)

if 'L_total' not in st.session_state: st.session_state.L_total = 30.0
if 'x_pos' not in st.session_state: st.session_state.x_pos = 0.0
if 'ea_correction' not in st.session_state: st.session_state.ea_correction = 1.0
if 'kp_correction' not in st.session_state: st.session_state.kp_correction = 1.0
if 'span_L' not in st.session_state: st.session_state.span_L = 30.0
if 'eta_bond' not in st.session_state: st.session_state.eta_bond = 0.8

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

# ==================== 强度：轴向拉力 ====================
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

# ==================== 强度：弯曲屈服 ====================
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

# ==================== 强度：压扁屈服 ====================
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
            # ---- 材料库下拉 ----
            if layer['type'] == '普通材料':
                mat_options = list(MATERIAL_LIBRARY_NORMAL.keys())
                selected_mat = st.selectbox(
                    "📚 快速填入材料典型值（室温）",
                    mat_options,
                    key=f"mat_select_{i}"
                )
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    if st.button("填入该材料", key=f"apply_mat_{i}") and selected_mat != "自定义":
                        mat = MATERIAL_LIBRARY_NORMAL[selected_mat]
                        df = layer['data'].copy()
                        df['弹性模量(MPa)'] = mat['E']
                        df['抗拉强度(MPa)'] = mat['sigma']
                        layer['data'] = df
                        st.rerun()
                with col_b:
                    if selected_mat != "自定义":
                        st.caption(f"E={MATERIAL_LIBRARY_NORMAL[selected_mat]['E']} MPa, σ={MATERIAL_LIBRARY_NORMAL[selected_mat]['sigma']} MPa")

            elif layer['type'] in ('编织层', '弹簧圈'):
                mat_options = list(MATERIAL_LIBRARY_WIRE.keys())
                selected_mat = st.selectbox(
                    "📚 快速填入丝材典型值（室温）",
                    mat_options,
                    key=f"mat_select_{i}"
                )
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    if st.button("填入该材料", key=f"apply_mat_{i}") and selected_mat != "自定义":
                        mat = MATERIAL_LIBRARY_WIRE[selected_mat]
                        df = layer['data'].copy()
                        df['丝材模量(MPa)'] = mat['E_f']
                        df['丝材抗拉强度(MPa)'] = mat['sigma_f']
                        layer['data'] = df
                        st.rerun()
                with col_b:
                    if selected_mat != "自定义":
                        st.caption(f"E_f={MATERIAL_LIBRARY_WIRE[selected_mat]['E_f']} MPa, σ_f={MATERIAL_LIBRARY_WIRE[selected_mat]['sigma_f']} MPa")

            # ---- 名称和类型 ----
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
                key=f"data_{i}_v17"
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
    if st.button("🔄 强制刷新计算", type="primary"):
        st.rerun()

    if st.button("恢复示例数据"):
        keys_to_clear = [k for k in list(st.session_state.keys())
                         if k.startswith("data_") or k.startswith("name_") or k.startswith("type_")
                         or k.startswith("mat_select_") or k.startswith("apply_mat_")
                         or k in ("ea_corr_input", "kp_corr_input", "span_L_input", "eta_bond_input",
                                  "new_type", "insert_pos", "add_layer_btn")]
        for k in keys_to_clear:
            del st.session_state[k]
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.session_state.ea_correction = 1.0
        st.session_state.kp_correction = 1.0
        st.session_state.span_L = 30.0
        st.session_state.eta_bond = 0.8
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层结构分析")

# 全局单位说明
st.caption(
    "**单位约定** — 长度: mm | 弹性模量/抗拉强度: MPa | 力: N | "
    "轴向刚度 EA: N | 弯曲刚度 EI: N·mm² | 抗压扁刚度 Kp: N/mm | 力矩 My: N·mm | "
    "温度: 室温 25°C（如需体温修正，请调整模量或修正系数）"
)

# ============================================================
# 📖 使用说明书（可折叠）
# ============================================================
with st.expander("📖 使用说明书（点击展开）", expanded=False):
    st.markdown("""
# 一、工具概览

本工具用于微导管多层结构的**刚度**和**强度**分析。

- **刚度**：描述导管抵抗变形的能力（EA 轴向、EI 弯曲、Kp 抗压扁）
- **强度**：描述导管能承受的极限载荷（Fu 轴向拉力、My 弯曲屈服、Fc 压扁屈服）

**注意**：本工具是**设计筛选工具**，不是实验替代品。绝对值需要一次实验标定（见第七节）。

---

# 二、单位约定

| 物理量 | 单位 |
|---|---|
| 长度、半径、壁厚、跨距 | mm |
| 弹性模量、抗拉强度 | MPa |
| 力、轴向刚度 EA | N |
| 弯曲刚度 EI | N·mm² |
| 抗压扁刚度 Kp | N/mm |
| 力矩 My | N·mm |

所有输入均按**室温 25°C** 处理。如需考虑体温（37°C），请手动下调模量（Pebax 大约降 20~30%）或使用修正系数。

---

# 三、界面布局

## 侧边栏（左侧）

- **导管总长度**：整根导管的总长（mm）
- **添加新层**：在指定位置插入新层
- **编辑各层**：每层可展开，包含：
  - **📚 快速填入材料典型值**（下拉菜单，一键填 E 和 σ_uts）
  - 名称、类型切换、删除
  - 数据表格（可动态增删行，实现沿轴向分段）
- **刚度修正系数**：EA、Kp 的实验标定折减
- **抗拉强度参数**：热熔填充粘接系数 η
- **三点弯曲试验参数**：跨距 L
- **强制刷新计算**、**恢复示例数据**

## 主区域（右侧）

- **轴向位置滑块**：选择截面位置
- **刚度分析**：三指标 + 三曲线 + 截面图 + 贡献图
- **强度分析**：三指标 + 三曲线 + 三张候选层表
- **参数明细表**：当前截面的所有层参数
- **导出**：CSV / Excel 下载

---

# 四、材料库

侧边栏每层的"📚 快速填入材料典型值"下拉菜单提供常见材料的室温典型值：

## 普通材料

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

## 丝材

| 材料 | E_f (MPa) | σ_f (MPa) |
|---|---|---|
| 不锈钢 304 (冷加工) | 193000 | 2200 |
| 不锈钢 316LVM (冷加工) | 193000 | 2400 |
| 镍钛合金 (超弹) | 60000 | 1200 |
| 钴铬合金 (L605) | 220000 | 2500 |
| 铂钨合金 | 170000 | 800 |

选择材料后点击"填入该材料"按钮，将材料参数覆盖到该层**所有行**。

---

# 五、刚度分析

## 5.1 三个指标

| 指标 | 单位 | 物理意义 |
|---|---|---|
| **Axial Stiffness EA** | N | 把导管拉长 100% 需要的力 |
| **Bending Stiffness EI** | N·mm² | 把导管弯成单位曲率需要的弯矩 |
| **Crush Stiffness Kp** | N/mm | 对径压力下直径减小 1 mm 需要的力 |

## 5.2 三张沿长度曲线

横轴是轴向位置（mm），纵轴分别是 EA、EI、Kp。

**读图要点**：
- **台阶**对应结构变化
- **灰色虚线**是当前滑块位置
- 曲线下降 = 缺少增强层（被热熔填充替代）

## 5.3 截面图

- **斜线**：编织层
- **叉线**：弹簧圈
- **点线**：热熔填充层
- **纯色**：普通材料层

## 5.4 贡献条形图

三张图分别显示每层对 EA、EI、Kp 的贡献百分比。**找出主力层**。

## 5.5 壁厚比提示

- 蓝框（< 0.1）：薄壁，Kp 可信
- 黄框（0.1~0.5）：厚壁，Kp 有 10~40% 偏差
- 红框（≥ 0.5）：极厚壁，需实验标定

---

# 六、强度分析

## 6.1 三个指标

| 指标 | 单位 | 物理意义 |
|---|---|---|
| **Axial Tensile Force Fu** | N | 拉断/拉屈服力 |
| **Bending Yield Moment My** | N·mm | 弯曲屈服力矩 |
| **Bending Yield Force (3-pt)** | N | 三点弯曲换算的力 |
| **Collapse Force Fc** | N | 压扁起始屈服力 |

## 6.2 弯曲屈服控制层

弯曲时各层**曲率相同**，表面应力 σ_i = E_z,i · κ · r_out,i。

令 σ_i = σ_uts,i 得 M_i = σ_uts,i · EI_total / (E_z,i · r_out,i)。

**谁 M_i 最小谁控制。** 最外层只满足 r_out 大，不一定控制。

## 6.3 压扁屈服控制层

各层**应变相同**，屈服应变为 ε_y,i = σ_uts,i / E_θ,i。

**谁 ε_y 最小谁控制。** 弹簧圈通常 E_θ 极高而 σ_uts 相对有限，ε_y 最小，所以是控制层。

## 6.4 轴向拉力贡献

每层 Fu 由两部分组成：
- **Fu_fiber**：丝材/弹簧贡献
- **Fu_matrix**：热熔填充贡献（通过 η 折减）

**弹簧圈层**：弹簧丝只占 ~13% 截面积，热熔填充占 ~87%，后者贡献往往更大。

**编织层**：丝材贡献 σ·A·V_f；热熔填充贡献 η·σ_hm·A·(1−V_f−V_matrix)。

---

# 七、修正系数

## 刚度修正系数

| 因素 | 典型折减 |
|---|---|
| 层间滑移 | 0.4~0.7 |
| 几何非线性 | 0.3~0.6 |
| 材料屈服 | 载荷越大折减越明显 |

**实验值通常是理论值的 30%~50%。**

## 抗拉粘接系数 η

热熔填充与丝材的粘接程度：
- η = 1.0：完全粘接
- η = 0.5：明显滑移
- η = 0.8：默认值（机械互锁，轻微滑移）

---

# 八、导出功能

主区域底部有三个导出按钮：

1. **当前截面参数表 CSV**：当前滑块位置的所有层参数
2. **沿长度曲线 CSV**：200 个采样点的 EA、EI、Kp、Fu、My、Fc
3. **完整报告 Excel**：包含输入参数、所有层数据、沿长度曲线（多 sheet）

Excel 导出需要 `openpyxl` 库（`pip install openpyxl`）。CSV 导出无依赖。

---

# 九、如何验证

## 刚度实验

| 刚度 | 实验方法 | 公式 |
|---|---|---|
| EA | 拉伸 | EA = k × L₀ |
| EI | 三点弯曲 | EI = FL³/(48δ) |
| Kp | 平板压缩 | Kp = F/ΔD |

## 强度实验

| 强度 | 实验方法 | 对应指标 |
|---|---|---|
| Fu | 拉伸至断裂 | 曲线最高点 |
| My | 三点弯曲至屈服 | 曲线偏离线性的点 |
| Fc | 平板压缩至屈服 | 曲线偏离线性的点 |

## 验证流程

1. 做一次标定实验
2. 修正系数 = 实测 / 理论
3. 填入工具
4. 再做一根不同结构的验证
5. 误差 < 20% 则工具可信

---

# 十、整体读图顺序

1. **拖滑块**到感兴趣的轴向位置
2. **看三个刚度指标**
3. **看刚度曲线**，了解整根导管的分布
4. **看截面图和贡献图**，找出主导层
5. **看强度指标和强度曲线**，评估安全裕度
6. **查候选层表格**，知道哪个层是强度控制层
7. **核对参数表**，确认输入无误
8. **导出报告**（如需要）

---

# 十一、常见问题

**Q1：算出来 Kp 太大？**
A：Kp 是线性小变形刚度，真实值需乘修正系数 0.3~0.5。

**Q2：为什么 Coil 层改了模量，强度 Fu 没变？**
A：Fu 只取决于抗拉强度 σ_uts，与弹性模量 E 无关。

**Q3：为什么弹簧圈层 Fu 有多个分量？**
A：弹簧圈层的轴向拉力 = 弹簧丝贡献 + 热熔填充贡献。后者往往更大。

**Q4：为什么弯曲屈服不是最外层控制？**
A：M_i = σ_uts,i · EI_total / (E_z,i · r_out,i)，谁 M_i 最小谁控制。

**Q5：为什么弹簧圈是压扁屈服控制层？**
A：弹簧圈屈服应变 ε_y = σ_uts/E_θ ≈ 8.5%，是所有层中最小的。

**Q6：改了参数图表没更新？**
A：按一次 Enter，或点「🔄 强制刷新计算」。

**Q7：为什么快速填入材料后还是旧值？**
A：点"填入该材料"按钮后会自动刷新。如果没刷新，再点一次「🔄 强制刷新计算」。

**Q8：Excel 导出报错？**
A：需要安装 openpyxl（`pip install openpyxl`）。或改用 CSV 导出。

---

# 十二、局限与不能做的事

| 场景 | 是否适用 |
|---|---|
| 相对比较两个设计方案 | ✅ 适用 |
| 参数扫描找最优点 | ✅ 适用 |
| 早期发现设计缺陷 | ✅ 适用 |
| 预测绝对刚度值 | ⚠️ 需要标定 |
| 报规格书 | ❌ 需实验 |
| 预测扭结精确位置 | ❌ 需有限元 |
| 疲劳寿命 | ❌ 需疲劳实验 |
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

x_pos_safe = min(max(st.session_state.x_pos, 0.0), L_total)
x_pos = st.slider("Axial position x (mm)", min_value=0.0, max_value=L_total,
                  value=x_pos_safe, step=0.5)
st.session_state.x_pos = x_pos

xs, EA_arr, EI_arr, Kp_arr, Fu_arr, My_arr, Fc_arr = compute_along_length(
    structure, L_total, ea_correction, kp_correction, eta_bond)

layers = compute_at_x(structure, x_pos, eta_bond=eta_bond)

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
    fig_s, axes_s = plt.subplots(3, 1, figsize=(10, 12))
    fig_s.suptitle("Stiffness Distribution along Catheter Length", y=0.98, fontsize=13)

    axes_s[0].plot(xs, EA_arr, 'b-', linewidth=2)
    axes_s[0].set_ylabel('EA (N)')
    axes_s[0].set_xlabel('Axial position (mm)')
    axes_s[0].set_title('Axial Stiffness')
    axes_s[0].grid(True); axes_s[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    axes_s[1].plot(xs, EI_arr, 'g-', linewidth=2)
    axes_s[1].set_ylabel('EI (N·mm²)')
    axes_s[1].set_xlabel('Axial position (mm)')
    axes_s[1].set_title('Bending Stiffness')
    axes_s[1].grid(True); axes_s[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    axes_s[2].plot(xs, Kp_arr, 'r-', linewidth=2)
    axes_s[2].set_ylabel('Kp (N/mm)')
    axes_s[2].set_xlabel('Axial position (mm)')
    axes_s[2].set_title(f'Crush Stiffness (correction × {kp_correction:.3f})')
    axes_s[2].grid(True); axes_s[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    fig_s.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_s)

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

    st.info(
        f"**弯曲屈服控制层**：{bending_ctrl}。"
        f" **压扁屈服控制层**：{collapse_ctrl}。"
    )

    st.subheader("Strength along Length")
    fig_t, axes_t = plt.subplots(3, 1, figsize=(10, 12))
    fig_t.suptitle("Strength Distribution along Catheter Length", y=0.98, fontsize=13)

    axes_t[0].plot(xs, Fu_arr, 'm-', linewidth=2)
    axes_t[0].set_ylabel('Fu (N)')
    axes_t[0].set_xlabel('Axial position (mm)')
    axes_t[0].set_title('Max Axial Tensile Force')
    axes_t[0].grid(True); axes_t[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    ax_my = axes_t[1]
    ax_my.plot(xs, My_arr, 'c-', linewidth=2, label='My')
    ax_my.set_ylabel('My (N·mm)', color='c')
    ax_my.set_xlabel('Axial position (mm)')
    ax_my.tick_params(axis='y', labelcolor='c')
    ax_my.set_title('Bending Yield Moment & Force')
    ax_my.grid(True); ax_my.axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    ax_my2 = ax_my.twinx()
    Fy_arr = 4 * My_arr / L_span if L_span > 0 else np.zeros_like(My_arr)
    ax_my2.plot(xs, Fy_arr, color='orange', linewidth=2, linestyle='--',
                label=f'Fy (3-pt, L={L_span:.0f} mm)')
    ax_my2.set_ylabel(f'Fy (N, L={L_span:.0f} mm)', color='orange')
    ax_my2.tick_params(axis='y', labelcolor='orange')

    axes_t[2].plot(xs, Fc_arr, 'y-', linewidth=2)
    axes_t[2].set_ylabel('Fc (N)')
    axes_t[2].set_xlabel('Axial position (mm)')
    axes_t[2].set_title('Collapse Force (weakest layer controls)')
    axes_t[2].grid(True); axes_t[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    fig_t.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_t)

    st.subheader("Bending Yield — Candidate Layers")
    st.caption(f"每层单独达到抗拉强度时所需的整体弯矩与三点弯曲力（L = {L_span:.1f} mm）。取最小值作为控制层。")
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
    st.caption("每层单独达到抗拉强度时所需的整体压扁力。取最小值作为控制层。")
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
    st.caption("弹簧圈/编织层的 Fu = 丝材贡献 + 热熔填充贡献（后者含 η 折减）。")
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

# 1. 当前截面参数表 CSV
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

# 2. 沿长度曲线 CSV
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

# 3. 完整报告 Excel
with exp_col3:
    if HAS_OPENPYXL:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Sheet 1: 概览
            overview_data = {
                '参数': ['导管总长度 (mm)', '当前轴向位置 (mm)', 'EA 修正系数',
                         'Kp 修正系数', '粘接系数 η', '三点弯曲跨距 (mm)'],
                '值': [L_total, x_pos, ea_correction, kp_correction, eta_bond, L_span]
            }
            pd.DataFrame(overview_data).to_excel(writer, sheet_name='概览', index=False)

            # Sheet 2: 当前截面刚度/强度
            if layers:
                cur_metrics = {
                    '指标': ['EA (N)', 'EI (N·mm²)', 'Kp (N/mm)', 'Fu (N)', 'My (N·mm)', 'Fc (N)'],
                    '值': [EA, EI, Kp, Fu, My, Fc]
                }
                pd.DataFrame(cur_metrics).to_excel(writer, sheet_name='当前截面指标', index=False)

            # Sheet 3: 当前截面参数表
            if not param_df.empty:
                param_df.to_excel(writer, sheet_name='当前截面参数', index=False)

            # Sheet 4: 沿长度曲线
            curve_df.to_excel(writer, sheet_name='沿长度曲线', index=False)

            # Sheet 5: 输入结构（原始数据）
            for i, layer in enumerate(structure):
                sheet_name = f'层{i+1}_{layer["name"]}'[:31]  # Excel sheet 名最多 31 字符
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

st.caption("CSV 用 UTF-8 with BOM 编码，Excel 打开不会乱码。Excel 报告包含概览、当前指标、截面参数、沿长度曲线、各层原始数据。")
