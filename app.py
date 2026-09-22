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

# ==================== 安全辅助函数 ====================
def safe_float(v, default=None):
    try:
        if v is None:
            return default
        if isinstance(v, str) and v.strip() == '':
            return default
        fv = float(v)
        if pd.isna(fv):
            return default
        return fv
    except (ValueError, TypeError):
        return default

def safe_seg_label(df_cur, j):
    try:
        row = df_cur.iloc[j]
        s = row.get('起始位置(mm)', None)
        e = row.get('结束位置(mm)', None)
        sf = safe_float(s, None)
        ef = safe_float(e, None)
        if sf is None or ef is None:
            return f"第 {j+1} 段"
        return f"第 {j+1} 段 ({sf:.1f} ~ {ef:.1f} mm)"
    except Exception:
        return f"第 {j+1} 段"

def sanitize_excel_sheet_name(name, max_len=31):
    for c in ['[', ']', '*', '?', '/', '\\', ':']:
        name = name.replace(c, '_')
    name = name.strip()
    if not name:
        name = "Sheet"
    return name[:max_len]

def clear_all_layer_keys():
    prefixes = ("data_", "name_", "type_", "mat_select_", "seg_select_",
                "apply_mat_", "dup_last_", "del_last_", "del_")
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in prefixes):
            del st.session_state[k]

# ==================== 参数校验 ====================
def check_parameters(structure, L_total, span_L):
    errors = []
    warnings = []

    for i, layer in enumerate(structure):
        df = layer['data']
        name = layer['name']
        if df is None or df.empty:
            errors.append(f"第 {i+1} 层（{name}）没有数据")
            continue
        for j, row in df.iterrows():
            try:
                start_raw = row.get('起始位置(mm)', None)
                end_raw = row.get('结束位置(mm)', None)
                r_in_raw = row.get('内半径(mm)', None)
                r_out_raw = row.get('外半径(mm)', None)
            except Exception:
                errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：读取失败")
                continue

            if (start_raw is None or pd.isna(start_raw)) and \
               (end_raw is None or pd.isna(end_raw)) and \
               (r_in_raw is None or pd.isna(r_in_raw)) and \
               (r_out_raw is None or pd.isna(r_out_raw)):
                continue

            start = safe_float(start_raw, None)
            end = safe_float(end_raw, None)
            r_in = safe_float(r_in_raw, None)
            r_out = safe_float(r_out_raw, None)

            missing = []
            if start is None: missing.append('起始位置')
            if end is None: missing.append('结束位置')
            if r_in is None: missing.append('内半径')
            if r_out is None: missing.append('外半径')
            if missing:
                errors.append(
                    f"第 {i+1} 层（{name}）第 {j+1} 段：以下字段缺失或非法（{'、'.join(missing)}）"
                )
                continue

            if start < 0:
                errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：起始位置为负（{start}）")
            if end <= start:
                errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：结束位置不大于起始位置（{start} → {end}）")
            if end > L_total + 1e-6:
                warnings.append(f"第 {i+1} 层（{name}）第 {j+1} 段：结束位置 {end} 超出导管总长 {L_total}")
            if r_in < 0:
                errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：内半径为负（{r_in}）")
            if r_out <= r_in:
                errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：外半径不大于内半径（{r_in} → {r_out}）")

            if layer['type'] == '普通材料':
                E = safe_float(row.get('弹性模量(MPa)', None), 0.0)
                sig = safe_float(row.get('抗拉强度(MPa)', None), 0.0)
                if E <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：弹性模量必须为正（当前 {E}）")
                if sig <= 0:
                    warnings.append(f"第 {i+1} 层（{name}）第 {j+1} 段：抗拉强度为 0 或负（{sig}），强度分析将跳过该层")
            elif layer['type'] == '编织层':
                E_f = safe_float(row.get('丝材模量(MPa)', None), 0.0)
                sig_f = safe_float(row.get('丝材抗拉强度(MPa)', None), 0.0)
                w_f = safe_float(row.get('扁丝宽度(mm)', None), 0.0)
                t_f = safe_float(row.get('扁丝厚度(mm)', None), 0.0)
                N = safe_float(row.get('股数', None), 0.0)
                if E_f <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：丝材模量必须为正（当前 {E_f}）")
                if sig_f <= 0:
                    warnings.append(f"第 {i+1} 层（{name}）第 {j+1} 段：丝材抗拉强度为 0 或负，强度分析将跳过该层")
                if w_f <= 0 or t_f <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：扁丝尺寸必须为正")
                if N <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：股数必须为正")
            elif layer['type'] == '弹簧圈':
                E_f = safe_float(row.get('丝材模量(MPa)', None), 0.0)
                sig_f = safe_float(row.get('丝材抗拉强度(MPa)', None), 0.0)
                d_w = safe_float(row.get('丝径(mm)', None), 0.0)
                pitch = safe_float(row.get('螺距(mm)', None), 0.0)
                if E_f <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：丝材模量必须为正")
                if sig_f <= 0:
                    warnings.append(f"第 {i+1} 层（{name}）第 {j+1} 段：丝材抗拉强度为 0 或负，强度分析将跳过该层")
                if d_w <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：丝径必须为正")
                if pitch <= 0:
                    errors.append(f"第 {i+1} 层（{name}）第 {j+1} 段：螺距必须为正")

    if structure and span_L > 0:
        max_r_out = 0
        for layer in structure:
            df = layer['data']
            if df is not None and not df.empty:
                try:
                    col_max = df['外半径(mm)'].apply(lambda v: safe_float(v, 0.0)).max()
                    if col_max is not None and not pd.isna(col_max):
                        max_r_out = max(max_r_out, float(col_max))
                except Exception:
                    pass
        D_outer = 2 * max_r_out
        if D_outer > 0:
            if span_L < 2 * D_outer:
                warnings.append(
                    f"三点弯曲跨距 L = {span_L:.1f} mm < 2 × 导管外径 = {2*D_outer:.2f} mm，"
                    f"剪切变形影响显著，Fy 换算误差可能较大"
                )
            elif span_L < 5 * D_outer:
                warnings.append(
                    f"三点弯曲跨距 L = {span_L:.1f} mm 偏小（建议 L ≥ 10 × 外径 = {10*D_outer:.1f} mm），"
                    f"请留意剪切修正"
                )

    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    return errors, warnings

# ==================== 会话状态 ====================
CURRENT_VERSION = "v40_name_sync"

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
    st.session_state.braid_crush_factor = 1.0
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
if 'braid_crush_factor' not in st.session_state: st.session_state.braid_crush_factor = 1.0
if 'saved_schemes' not in st.session_state: st.session_state.saved_schemes = []

# ==================== 分段查找 ====================
def find_segment(df, x):
    if df is None or df.empty:
        return None
    for _, row in df.iterrows():
        try:
            s = safe_float(row.get('起始位置(mm)', None), None)
            e = safe_float(row.get('结束位置(mm)', None), None)
            if s is None or e is None:
                continue
            if s <= x <= e:
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
            r_out_v = safe_float(row.get('外半径(mm)', None), None)
            E_v = safe_float(row.get('弹性模量(MPa)', None), None)
            sig_v = safe_float(row.get('抗拉强度(MPa)', None), 0.0)
            if r_out_v is None or r_out_v <= 0 or E_v is None:
                continue
            candidates.append((r_out_v, E_v, sig_v if sig_v is not None else 0.0))
    if not candidates:
        return None, None
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1], candidates[0][2]

def get_reference_radius(structure, layer_type_name):
    refs = []
    for layer in structure:
        if layer['type'] != layer_type_name:
            continue
        df = layer['data']
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            r_in_v = safe_float(row.get('内半径(mm)', None), None)
            r_out_v = safe_float(row.get('外半径(mm)', None), None)
            if r_in_v is None or r_out_v is None:
                continue
            if r_out_v <= r_in_v or r_out_v <= 0:
                continue
            refs.append((r_in_v, r_out_v))
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
    if E_hm is None or pd.isna(E_hm): E_hm = 0.0
    w = safe_float(row.get('扁丝宽度(mm)', None), 0.0)
    t = safe_float(row.get('扁丝厚度(mm)', None), 0.0)
    N = safe_float(row.get('股数', None), 0.0)
    n_s = safe_float(row.get('每束根数', None), 1.0)
    PPI = safe_float(row.get('每英寸交叉数', None), 0.0)
    E_f = safe_float(row.get('丝材模量(MPa)', None), 0.0)
    r_in = safe_float(row.get('内半径(mm)', None), 0.0)
    r_out = safe_float(row.get('外半径(mm)', None), 0.0)
    V_matrix = safe_float(row.get('原始基体体积分数', None), 0.0)

    alpha = compute_braid_angle(r_in, r_out, PPI, N)
    alpha_rad = np.radians(alpha)

    denom = np.pi * (r_out**2 - r_in**2) * np.cos(alpha_rad)
    if denom > 0:
        V_f_raw = 2 * N * n_s * w * t / denom
        V_f = min(1.0, V_f_raw) if not pd.isna(V_f_raw) else 0.0
    else:
        V_f = 0.0

    V_void = max(0.0, 1.0 - V_f - V_matrix)
    E_m_eff = E_hm * V_void / (V_void + V_matrix) if (V_void + V_matrix) > 0 else 0.0

    E_z = E_f * V_f * (np.cos(alpha_rad)**4) + E_m_eff * (1 - V_f)
    E_theta = E_f * V_f * (np.sin(alpha_rad)**4) + E_m_eff * (1 - V_f)
    return E_z, E_theta, V_f, V_void, alpha

# ==================== 弹簧圈模量 ====================
def compute_coil_moduli(row, E_hm):
    if E_hm is None or pd.isna(E_hm): E_hm = 0.0
    d = safe_float(row.get('丝径(mm)', None), 0.0)
    pitch = safe_float(row.get('螺距(mm)', None), 0.0)
    E_f = safe_float(row.get('丝材模量(MPa)', None), 0.0)
    r_in = safe_float(row.get('内半径(mm)', None), 0.0)
    r_out = safe_float(row.get('外半径(mm)', None), 0.0)
    V_matrix = safe_float(row.get('原始基体体积分数', None), 0.0)

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
def compute_at_x(structure, x, eta_bond=1.0, braid_crush_factor=1.0):
    hot_melt_E, hot_melt_sigma = find_hot_melt_props(structure, x)
    layers = []
    has_braid_here = False
    has_coil_here = False

    for idx, layer in enumerate(structure):
        try:
            row = find_segment(layer['data'], x)
            if row is None:
                continue
            ltype = layer['type']
            if ltype == '编织层': has_braid_here = True
            elif ltype == '弹簧圈': has_coil_here = True

            alpha = None; V_void = None
            Fu_override = None
            Fu_fiber = 0.0
            Fu_matrix_contrib = 0.0
            r_in_v = safe_float(row.get('内半径(mm)', None), None)
            r_out_v = safe_float(row.get('外半径(mm)', None), None)
            if r_in_v is None or r_out_v is None or r_out_v <= r_in_v:
                continue
            A_total = np.pi * (r_out_v**2 - r_in_v**2)

            if ltype == '普通材料':
                E_z = safe_float(row.get('弹性模量(MPa)', None), None)
                if E_z is None or E_z <= 0:
                    continue
                E_theta = E_z
                V_f = None
                sigma_uts = safe_float(row.get('抗拉强度(MPa)', None), 0.0)
            elif ltype == '编织层':
                E_z, E_theta, V_f, V_void, alpha = compute_braid_moduli(row, hot_melt_E)
                E_theta = E_theta * braid_crush_factor
                sigma_uts = safe_float(row.get('丝材抗拉强度(MPa)', None), 0.0)
                V_f_val = V_f if V_f is not None else 0.0
                Fu_fiber = sigma_uts * A_total * V_f_val
                V_matrix = safe_float(row.get('原始基体体积分数', None), 0.0)
                if hot_melt_sigma is not None:
                    Fu_matrix_contrib = hot_melt_sigma * A_total * (1.0 - V_f_val - V_matrix) * eta_bond
                Fu_override = Fu_fiber + Fu_matrix_contrib
            elif ltype == '弹簧圈':
                E_z, E_theta, V_f, V_void = compute_coil_moduli(row, hot_melt_E)
                sigma_uts = safe_float(row.get('丝材抗拉强度(MPa)', None), 0.0)
                d_wire_v = safe_float(row.get('丝径(mm)', None), 0.0)
                pitch_v = safe_float(row.get('螺距(mm)', None), 0.0)
                Fu_fiber = compute_coil_tensile_force(sigma_uts, d_wire_v, pitch_v, r_in_v, r_out_v)
                V_spring = V_f if V_f is not None else 0.0
                V_matrix = safe_float(row.get('原始基体体积分数', None), 0.0)
                if hot_melt_sigma is not None:
                    Fu_matrix_contrib = hot_melt_sigma * A_total * (1.0 - V_spring - V_matrix) * eta_bond
                Fu_override = Fu_fiber + Fu_matrix_contrib
            else:
                continue

            if pd.isna(E_z) or pd.isna(E_theta):
                continue

            layers.append({
                'name': layer['name'], 'type': ltype,
                'r_in': r_in_v, 'r_out': r_out_v,
                'E_z': float(E_z), 'E_theta': float(E_theta),
                'V_f': V_f, 'V_void': V_void,
                'alpha': alpha, 'sigma_uts': float(sigma_uts if not pd.isna(sigma_uts) else 0.0),
                'Fu_override': Fu_override,
                'Fu_fiber': Fu_fiber, 'Fu_matrix': Fu_matrix_contrib,
                'layer_idx': idx, 'is_filler': False
            })
        except Exception:
            continue

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
    if t <= 0:
        return 0.0
    R_mid = (r_in + r_out) / 2
    if R_mid <= 0:
        return 0.0
    if r_in <= 1e-9:
        return E_theta * t**3 / 12
    tr = t / R_mid
    if tr < 0.1:
        return E_theta * t**3 / 12
    try:
        r_n = t / np.log(r_out / r_in)
    except (ValueError, ZeroDivisionError):
        return E_theta * t**3 / 12
    e = R_mid - r_n
    if e <= 0:
        return E_theta * t**3 / 12
    return E_theta * t * e * r_n

def compute_wall_axial_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    return E_theta * t if t > 0 else 0.0

# ==================== 厚壁：有效几何常数 ====================
def compute_effective_const(tr):
    const_thin = np.pi / 4 - 2 / np.pi
    return const_thin * (1.0 + 0.5 * tr + 1.0 * tr * tr)

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

        const_eff = compute_effective_const(thick_ratio)

        compliance = 0.0
        if EI_theta_bend > 0:
            compliance += const_eff * R**3 / EI_theta_bend
        if EA_theta > 0:
            compliance += const_eff * R / EA_theta
        Kp_raw = 1.0 / compliance if compliance > 0 else 0.0

        if thick_ratio < 0.08:
            model_used = "thin-wall"
        elif thick_ratio < 0.15:
            model_used = "transition"
        else:
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

def compute_axial_yield(layers, ea_corr=1.0):
    if not layers:
        return 0.0, None, [], []
    valid_indices = [i for i, l in enumerate(layers)
                     if l.get('sigma_uts', 0.0) > 0 and l['E_z'] > 0]
    if not valid_indices:
        return 0.0, None, [], []

    A_list, EA_list = [], []
    for l in layers:
        A_i = np.pi * (l['r_out']**2 - l['r_in']**2)
        A_list.append(A_i)
        EA_list.append(l['E_z'] * A_i)

    EA_theory = sum(EA_list[i] for i in valid_indices)
    if EA_theory <= 0:
        return 0.0, None, [], []

    candidates = []
    for i in valid_indices:
        l = layers[i]
        E_z = l['E_z']
        sigma_uts = l.get('sigma_uts', 0.0)
        candidates.append({
            'layer': l['name'], 'eps_y': sigma_uts / E_z,
            'E_z': E_z, 'sigma_uts': sigma_uts
        })

    candidates.sort(key=lambda c: c['eps_y'])
    eps_y_min = candidates[0]['eps_y']
    ctrl_layer = candidates[0]['layer']
    Fu_y = EA_theory * ea_corr * eps_y_min

    contributions = []
    for i, l in enumerate(layers):
        is_valid = (i in valid_indices)
        if is_valid:
            EA_contrib = EA_list[i]
            F_i = EA_contrib * ea_corr * eps_y_min
            pct = EA_contrib / EA_theory * 100 if EA_theory > 0 else 0
        else:
            F_i = 0.0; pct = 0.0
        contributions.append({
            'layer': l['name'],
            'E_z': l['E_z'],
            'sigma_uts': l.get('sigma_uts', 0.0),
            'eps_y': l.get('sigma_uts', 0.0) / l['E_z'] if l['E_z'] > 0 else 0,
            'F_i': F_i, 'pct': pct,
            'is_ctrl': (l['name'] == ctrl_layer),
            'is_valid': is_valid,
        })
    return Fu_y, ctrl_layer, candidates, contributions

def compute_bending_yield(layers):
    if not layers:
        return 0.0, None, [], []
    valid_indices = [i for i, l in enumerate(layers)
                     if l.get('sigma_uts', 0.0) > 0
                     and l['E_z'] > 0 and l['r_out'] > 0]
    if not valid_indices:
        return 0.0, None, [], []

    EI_list = []
    for l in layers:
        I_i = (np.pi / 4) * (l['r_out']**4 - l['r_in']**4)
        EI_list.append(l['E_z'] * I_i)

    EI_total = sum(EI_list[i] for i in valid_indices)
    if EI_total <= 0:
        return 0.0, None, [], []

    candidates = []
    for i in valid_indices:
        l = layers[i]
        E_i = l['E_z']; r_out = l['r_out']
        sigma_uts = l.get('sigma_uts', 0.0)
        M_i = sigma_uts * EI_total / (E_i * r_out)
        candidates.append({
            'layer': l['name'], 'M_y': M_i, 'E_z': E_i,
            'r_out': r_out, 'sigma_uts': sigma_uts,
            'EI_i': EI_list[i]
        })

    candidates.sort(key=lambda c: c['M_y'])
    M_y = candidates[0]['M_y']
    ctrl_layer = candidates[0]['layer']

    contributions = []
    for i, l in enumerate(layers):
        is_valid = (i in valid_indices)
        EI_i = EI_list[i]
        if is_valid:
            M_actual = EI_i * M_y / EI_total
            pct = EI_i / EI_total * 100
        else:
            M_actual = 0.0; pct = 0.0
        contributions.append({
            'layer': l['name'], 'EI_i': EI_i,
            'M_actual': M_actual, 'pct': pct,
            'is_ctrl': (l['name'] == ctrl_layer),
            'is_valid': is_valid,
        })
    return M_y, ctrl_layer, candidates, contributions

def compute_collapse_force(layers):
    if not layers:
        return 0.0, None, [], []
    valid_indices = [i for i, l in enumerate(layers)
                     if l.get('sigma_uts', 0.0) > 0
                     and l['E_theta'] > 0
                     and (l['r_out'] - l['r_in']) > 0]
    if not valid_indices:
        return 0.0, None, [], []

    EI_theta_list = []
    for l in layers:
        EI_theta_list.append(
            compute_wall_bending_stiffness(l['E_theta'], l['r_in'], l['r_out'])
        )
    EI_theta_total = sum(EI_theta_list[i] for i in valid_indices)
    if EI_theta_total <= 0:
        return 0.0, None, [], []

    r0 = min(l['r_in'] for l in layers)
    rn = max(l['r_out'] for l in layers)
    R = (r0 + rn) / 2
    C = 0.318

    candidates = []
    for i in valid_indices:
        l = layers[i]
        E_theta = l['E_theta']; t_i = l['r_out'] - l['r_in']
        sigma_uts = l.get('sigma_uts', 0.0)
        F_i = sigma_uts * EI_theta_total * 2 / (E_theta * C * R * t_i)
        candidates.append({
            'layer': l['name'], 'F_c': F_i, 'E_theta': E_theta,
            't': t_i, 'sigma_uts': sigma_uts,
            'EI_theta_i': EI_theta_list[i]
        })

    candidates.sort(key=lambda c: c['F_c'])
    F_c = candidates[0]['F_c']
    ctrl_layer = candidates[0]['layer']

    M_max = C * F_c * R
    contributions = []
    for i, l in enumerate(layers):
        is_valid = (i in valid_indices)
        EI_theta_i = EI_theta_list[i]
        if is_valid:
            M_actual = EI_theta_i * M_max / EI_theta_total
            pct = EI_theta_i / EI_theta_total * 100
        else:
            M_actual = 0.0; pct = 0.0
        contributions.append({
            'layer': l['name'], 'EI_theta_i': EI_theta_i,
            'M_actual': M_actual, 'pct': pct,
            'is_ctrl': (l['name'] == ctrl_layer),
            'is_valid': is_valid,
        })
    return F_c, ctrl_layer, candidates, contributions

# ==================== 非线性力-位移模型 ====================
def compute_crush_force_nonlinear(Kp, D_outer, dD, c=1.0):
    if D_outer <= 0:
        return Kp * dD
    dD = np.asarray(dD)
    return Kp * dD / (1.0 + c * dD / D_outer)

# ==================== 沿长度扫描 ====================
def compute_along_length(structure, L_total, ea_corr=1.0, kp_corr=1.0, eta_bond=1.0,
                          braid_crush_factor=1.0, n=200):
    xs = np.linspace(0, L_total, n)
    EA_arr = np.zeros(n); EI_arr = np.zeros(n); Kp_arr = np.zeros(n)
    Fu_arr = np.zeros(n); My_arr = np.zeros(n); Fc_arr = np.zeros(n)
    for i, x in enumerate(xs):
        try:
            layers = compute_at_x(structure, x, eta_bond=eta_bond,
                                  braid_crush_factor=braid_crush_factor)
            EA, EI, Kp, _, _, _, _, _ = compute_stiffness(layers, ea_corr, kp_corr)
            Fu, _ = compute_axial_strength(layers)
            My, _, _, _ = compute_bending_yield(layers)
            Fc, _, _, _ = compute_collapse_force(layers)
            EA_arr[i] = EA; EI_arr[i] = EI; Kp_arr[i] = Kp
            Fu_arr[i] = Fu; My_arr[i] = My; Fc_arr[i] = Fc
        except Exception:
            continue
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
                try:
                    r_out_ref = safe_float(st.session_state.structure[0]['data'].iloc[0].get('外半径(mm)', None), 0.4)
                    r_in_ref = safe_float(st.session_state.structure[-1]['data'].iloc[0].get('内半径(mm)', None), 0.27)
                except Exception:
                    r_out_ref, r_in_ref = 0.4, 0.27
            else:
                r_out_ref, r_in_ref = 0.4, 0.27
            new_layer = {'name': f'Layer {len(st.session_state.structure)+1}',
                         'type': new_type,
                         'data': make_default_layer(new_type, L_total, r_in_ref, r_out_ref)}
            st.session_state.structure.insert(int(insert_pos), new_layer)
            clear_all_layer_keys()
            st.rerun()

    st.markdown("---")
    st.markdown("**编辑各层**")

    for i, layer in enumerate(st.session_state.structure):
        # 防御性检查：type 必须在已知类型里
        if layer.get('type') not in LAYER_TYPES:
            layer['type'] = '普通材料'
            layer['data'] = make_default_layer('普通材料', L_total)

        # ============================================================
        # v40 修复：在渲染 expander 之前，从 session_state 同步最新名称
        # 这样 expander 标题与 text_input 显示的名称保持一致
        # ============================================================
        ss_name_key = f"name_{i}"
        if ss_name_key in st.session_state:
            ss_name = st.session_state[ss_name_key]
            if isinstance(ss_name, str):
                stripped = ss_name.strip()
                if stripped != '' and stripped != layer.get('name', ''):
                    layer['name'] = stripped
        name_for_title = layer.get('name', '') or f'Layer {i+1}'

        with st.expander(f"第{i+1}层：{name_for_title}（{layer['type']}）", expanded=False):
            if layer['type'] == '普通材料':
                mat_options = list(MATERIAL_LIBRARY_NORMAL.keys())
                selected_mat = st.selectbox("📚 材料库（室温典型值）", mat_options, key=f"mat_select_{i}")
                df_cur = layer['data']
                n_rows = len(df_cur)
                if n_rows > 0 and selected_mat != "自定义":
                    seg_labels = ["🎯 全部段"] + [safe_seg_label(df_cur, j) for j in range(n_rows)]
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
                                try:
                                    seg_idx = seg_labels.index(selected_seg) - 1
                                except ValueError:
                                    seg_idx = -1
                                if 0 <= seg_idx < len(df_new):
                                    df_new.loc[df_new.index[seg_idx], '弹性模量(MPa)'] = mat['E']
                                    df_new.loc[df_new.index[seg_idx], '抗拉强度(MPa)'] = mat['sigma']
                            layer['data'] = df_new
                            editor_key_clear = f"data_{i}_{layer['type']}_v40"
                            if editor_key_clear in st.session_state:
                                del st.session_state[editor_key_clear]
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
                    seg_labels = ["🎯 全部段"] + [safe_seg_label(df_cur, j) for j in range(n_rows)]
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
                                try:
                                    seg_idx = seg_labels.index(selected_seg) - 1
                                except ValueError:
                                    seg_idx = -1
                                if 0 <= seg_idx < len(df_new):
                                    df_new.loc[df_new.index[seg_idx], '丝材模量(MPa)'] = mat['E_f']
                                    df_new.loc[df_new.index[seg_idx], '丝材抗拉强度(MPa)'] = mat['sigma_f']
                            layer['data'] = df_new
                            editor_key_clear = f"data_{i}_{layer['type']}_v40"
                            if editor_key_clear in st.session_state:
                                del st.session_state[editor_key_clear]
                            st.rerun()
                with col_b:
                    if selected_mat != "自定义":
                        st.caption(f"E_f = {MATERIAL_LIBRARY_WIRE[selected_mat]['E_f']} MPa, σ_f = {MATERIAL_LIBRARY_WIRE[selected_mat]['sigma_f']} MPa")

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                # v40：text_input 的 key 复用 ss_name_key
                new_name = st.text_input("名称（图表中显示）", value=layer['name'], key=ss_name_key)
                if new_name != layer['name']:
                    layer['name'] = new_name
            with col2:
                try:
                    cur_type_idx = list(LAYER_TYPES.keys()).index(layer['type'])
                except ValueError:
                    cur_type_idx = 0
                new_type = st.selectbox("类型", list(LAYER_TYPES.keys()),
                                        index=cur_type_idx, key=f"type_{i}")
                if new_type != layer['type']:
                    old = layer['data'].iloc[0].to_dict() if len(layer['data']) > 0 else {}
                    r_in = safe_float(old.get('内半径(mm)', None), 0.27)
                    r_out = safe_float(old.get('外半径(mm)', None), 0.3048)
                    start = safe_float(old.get('起始位置(mm)', None), 0.0)
                    end = safe_float(old.get('结束位置(mm)', None), L_total)
                    old_key = f"data_{i}_{layer['type']}_v40"
                    if old_key in st.session_state:
                        del st.session_state[old_key]
                    layer['type'] = new_type
                    layer['data'] = make_default_layer(new_type, end, r_in, r_out)
                    if len(layer['data']) > 0:
                        layer['data'].loc[layer['data'].index[0], '起始位置(mm)'] = start
                    st.rerun()
            with col3:
                if st.button("删除", key=f"del_{i}"):
                    st.session_state.structure.pop(i)
                    clear_all_layer_keys()
                    st.rerun()

            st.caption(LAYER_TYPES[layer['type']]['caption'])

            editor_key = f"data_{i}_{layer['type']}_v40"

            if editor_key in st.session_state:
                cached = st.session_state[editor_key]
                if isinstance(cached, pd.DataFrame):
                    try:
                        if (list(cached.columns) == list(layer['data'].columns)
                                and not cached.equals(layer['data'])):
                            layer['data'] = cached.copy()
                    except Exception:
                        pass

            edited = st.data_editor(
                layer['data'],
                num_rows="dynamic",
                use_container_width=True,
                key=editor_key
            )
            if edited is not None:
                layer['data'] = edited.copy()

            col_dup, col_del_last, col_hint = st.columns([1.2, 1.2, 2])
            with col_dup:
                if st.button("📋 复制最后一行", key=f"dup_last_{i}",
                             help="把本层最后一行数据复制一份，追加到本层末尾。"
                                  "新行的\"起始位置\"自动接续上一行的\"结束位置\"。"):
                    if len(layer['data']) > 0:
                        last_row = layer['data'].iloc[-1].to_dict()
                        last_end = safe_float(last_row.get('结束位置(mm)', None), None)
                        if last_end is not None:
                            last_row['起始位置(mm)'] = last_end
                        new_row_df = pd.DataFrame([last_row])
                        try:
                            new_row_df = new_row_df[list(layer['data'].columns)]
                        except Exception:
                            pass
                        layer['data'] = pd.concat(
                            [layer['data'], new_row_df], ignore_index=True
                        )
                        if editor_key in st.session_state:
                            del st.session_state[editor_key]
                        st.rerun()
            with col_del_last:
                if st.button("🗑️ 删除最后一行", key=f"del_last_{i}",
                             help="删除本层最后一行。至少保留一行。"):
                    if len(layer['data']) > 1:
                        layer['data'] = layer['data'].iloc[:-1].reset_index(drop=True)
                        if editor_key in st.session_state:
                            del st.session_state[editor_key]
                        st.rerun()
                    else:
                        st.warning("至少保留一行。")
            with col_hint:
                st.caption("💡 复制后请手动修改起止位置、材料参数等。")

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
    st.caption(
        "🔧 厚壁修正：有效几何常数随 t/R 连续变化"
        "（薄壁 0.1488 → t/R=0.3 约 0.1845），"
        "Kp 公式统一为柔度叠加，t/R = 0.1 附近无跳变。"
    )

    st.markdown("---")
    st.markdown("**编织层压扁折减**")
    braid_crush_factor = st.number_input(
        "编织层环向模量折减系数",
        min_value=0.1, max_value=1.0,
        value=float(st.session_state.braid_crush_factor),
        step=0.05, format="%.2f",
        key="braid_crush_factor_input"
    )
    st.session_state.braid_crush_factor = braid_crush_factor
    st.caption("编织层为网眼结构，受压时局部先塌陷。折减系数作用于编织层的环向模量 E_θ，"
               "影响 Kp 和 Fc。1.0 = 不折减；0.7 = 折减 30%。")

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
    st.caption("c = 0：完全线性；c = 1：中等软化（默认）；c = 3：强软化")

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
                'span_L': span_L,
                'braid_crush_factor': braid_crush_factor
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
                st.caption(f"{idx+1}. {s['name']}")
            with col_load:
                if st.button("载入", key=f"load_scheme_{idx}"):
                    st.session_state.structure = copy.deepcopy(s['structure'])
                    st.session_state.L_total = s['L_total']
                    st.session_state.ea_correction = s['ea_correction']
                    st.session_state.kp_correction = s['kp_correction']
                    st.session_state.eta_bond = s['eta_bond']
                    st.session_state.softening_c = s['softening_c']
                    st.session_state.span_L = s['span_L']
                    st.session_state.braid_crush_factor = s.get('braid_crush_factor', 1.0)
                    clear_all_layer_keys()
                    st.rerun()
            with col_del:
                if st.button("删除", key=f"del_scheme_{idx}"):
                    st.session_state.saved_schemes.pop(idx)
                    st.rerun()

    st.markdown("---")
    if st.button("🔄 强制刷新计算", key="refresh_btn"):
        st.rerun()

    if st.button("恢复示例数据", key="reset_btn"):
        clear_all_layer_keys()
        keys_to_clear = [k for k in list(st.session_state.keys())
                         if k in ("ea_corr_input", "kp_corr_input", "span_L_input", "eta_bond_input",
                                  "softening_c_input", "braid_crush_factor_input",
                                  "new_type", "insert_pos", "add_layer_btn", "scheme_name_input")]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.session_state.ea_correction = 1.0
        st.session_state.kp_correction = 1.0
        st.session_state.span_L = 30.0
        st.session_state.eta_bond = 0.8
        st.session_state.softening_c = 1.0
        st.session_state.braid_crush_factor = 1.0
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层结构分析")

st.caption(
    "**单位约定** — 长度: mm | 弹性模量/抗拉强度: MPa | 力: N | "
    "轴向刚度 EA: N | 弯曲刚度 EI: N·mm² | 抗压扁刚度 Kp: N/mm | 力矩 My: N·mm"
)

structure = st.session_state.structure
L_total = st.session_state.L_total
ea_correction = st.session_state.ea_correction
kp_correction = st.session_state.kp_correction
L_span = st.session_state.span_L
eta_bond = st.session_state.eta_bond
softening_c = st.session_state.softening_c
braid_crush_factor = st.session_state.braid_crush_factor
saved_schemes = st.session_state.saved_schemes

errors_check, warnings_check = check_parameters(structure, L_total, L_span)
if errors_check:
    with st.expander(f"❌ 参数校验：发现 {len(errors_check)} 个错误", expanded=True):
        for e in errors_check:
            st.error(e)
if warnings_check:
    with st.expander(f"⚠️ 参数校验：发现 {len(warnings_check)} 个警告", expanded=False):
        for w in warnings_check:
            st.warning(w)

# ============================================================
# 📖 使用说明书
# ============================================================
st.markdown("## 📖 使用说明书")
st.caption("每个模块独立展开。建议先看第 1 节快速开始，标定时看第 9 节。")

with st.expander("1. 快速开始", expanded=False):
    st.markdown("""
**五分钟上手：**

1. **看默认结构**：程序启动时已加载 3 层示例结构（Hot Melt → 弹簧圈 → PTFE）
2. **拖动滑块**：主区域中间的 "Axial position x (mm)" 滑块可查看不同位置
3. **看六个指标**：顶部有 EA/EI/Kp + Fu/My/Fc 六个指标
4. **改参数**：侧边栏展开任意层修改数值
5. **保存方案**：改好后在 "💾 方案管理" 保存

**分段设置**：每层底部有"📋 复制最后一行"按钮，点击后自动复制上一行作为新段，
新段"起始位置"自动接续上一段的"结束位置"。也有"🗑️ 删除最后一行"按钮。

**参数校验**：程序启动时会自动检查参数合理性，错误和警告显示在顶部。
    """)

with st.expander("2. 界面总览", expanded=False):
    st.markdown("""
**主区域：**

| 区块 | 内容 |
|---|---|
| 单位约定 | 全局单位说明 |
| 参数校验 | 自动检查错误和警告 |
| 使用说明书 | 分模块展开 |
| 轴向位置滑块 | 选择截面位置 |
| 刚度分析 | 3 指标 + 3 曲线 + 力-位移曲线 + 方案对比 + 截面图 + 各层贡献图和表 |
| 强度分析 | 拉伸起始屈服 + 弯曲屈服 + 压扁屈服 + 各层贡献表 |
| 参数明细表 | 当前截面所有层参数 |
| 导出功能 | 3 个导出按钮 |

**侧边栏：** 导管结构定义、刚度修正系数、编织层压扁折减、抗压扁非线性参数、抗拉强度参数、三点弯曲试验参数、方案管理。
    """)

with st.expander("3. 输入参数详解", expanded=False):
    st.markdown("""
**普通材料**：起始/结束位置、内/外半径、弹性模量、抗拉强度。

**编织层**：起始/结束位置、内/外半径、扁丝宽度/厚度、股数、每束根数、每英寸交叉数、丝材模量、丝材抗拉强度、原始基体体积分数。

**弹簧圈**：起始/结束位置、内/外半径、丝径、螺距、丝材模量、丝材抗拉强度、原始基体体积分数。
    """)

with st.expander("4. 材料库使用", expanded=False):
    st.markdown("""
每层顶部有"📚 材料库"下拉菜单。选材料 → 选应用范围 → 点"填入"。

**普通材料**：PTFE（块体/挤出管）、Pebax 2533/3533/5533/6333/7233、尼龙 12/6、聚氨酯、HDPE。

**丝材**：不锈钢 304/316LVM（冷加工）、镍钛合金、钴铬合金 L605、铂钨合金。

**多段结构**：每层表格下方有"📋 复制最后一行"、"🗑️ 删除最后一行"按钮。
    """)

with st.expander("5. 刚度分析", expanded=False):
    st.markdown("""
三个刚度指标：EA (N)、EI (N·mm²)、Kp (N/mm)。

**各层刚度贡献明细表**：显示每层对 EA、EI、Kp 的贡献值和占比，附合计行。

**厚壁修正（v34+）**：有效几何常数 const_eff 随 t/R 连续变化。Kp 使用统一柔度叠加公式，t/R = 0.1 附近无跳变。
    """)

with st.expander("6. 强度分析", expanded=False):
    st.markdown("""
**三种强度模式：**

| 模式 | 指标 | 是否有控制层 |
|---|---|---|
| 拉伸起始屈服 | Fu_y | 有 |
| 弯曲屈服 | My | 有 |
| 压扁屈服 | Fc | 有 |

**拉伸起始屈服**：各层屈服应变 ε_y = σ_uts/E_z 最小的层控制。σ_uts ≤ 0 的层不参与强度分析。

**弯曲屈服**：控制层由 M_i = σ_uts,i · EI_total / (E_z,i · r_out,i) 决定，取最小。

**压扁屈服**：控制层由 ε_y = σ_uts/E_θ 决定，取最小。

**轴向拉力**：另有整体极限 Fu，是各层贡献相加。
    """)

with st.expander("7. 非线性力-位移曲线", expanded=False):
    st.markdown("""
F(ΔD) = Kp · ΔD / (1 + c · ΔD / D)

软化系数 c：0（线性）、0.5（轻微）、1.0（中等，默认）、2.0（明显）、3.0（强软化）。
    """)

with st.expander("8. 修正系数一览", expanded=False):
    st.markdown("""
| 系数 | 作用 | 默认值 |
|---|---|---|
| EA 修正 | 修正轴向刚度 | 1.0 |
| Kp 修正 | 修正抗压扁刚度 | 1.0 |
| 编织层压扁折减 | 编织层环向模量折减 | 1.0 |
| 粘接系数 η | 热熔填充拉力修正 | 0.8 |
| 软化系数 c | 力-位移曲线软化 | 1.0 |
| 跨距 L | 三点弯曲实验支点距离 | 30 mm |
    """)

with st.expander("9. 实验标定流程（详细步骤）", expanded=False):
    st.markdown("""
## 9.1 准备工作

**设备**：万能材料试验机、拉伸夹具、平板压缩夹具、三点弯曲夹具、游标卡尺。

**样品**：至少 3 根同批次导管。

---

## 9.2 拉伸实验（标定 EA 修正 + 粘接系数 η）

1. 取一段导管，长度 L₀ = 100 mm
2. 两端插入金属芯轴，用锥形夹头夹住
3. 以 1 mm/min 恒定速度拉伸
4. 记录力 F 和位移 δ 完整曲线
5. 至少测 3 根，取平均

**EA 实测** = 初始线性段斜率 k × L₀
**EA 修正系数** = EA 实测 / EA 理论

**粘接系数 η**：由 Fu_实测 反推

---

## 9.3 平板压缩实验（标定 Kp 修正 + 软化系数 c）

1. 取短导管 5~10 mm
2. 放在两块平行平板之间
3. 恒定速度下压，记录力 F 和直径减小量 ΔD

**Kp 实测** = 初始线性段斜率
**Kp 修正系数** = Kp 实测 / Kp 理论

⚠️ **v34+ 提醒**：厚壁改进后 Kp 理论值系统性降低。若之前已标定过 kp_correction，需重新标定。

**软化系数 c** = 2D(r - 0.5) / (1 - r)

---

## 9.4 三点弯曲跨距 L

卡尺量三点弯曲夹具两支撑点距离。

---

## 9.5 完整标定示例

| 项目 | 数值 |
|---|---|
| 拉伸长度 L₀ | 100 mm |
| 拉伸初始斜率 k | 0.28 N/mm |
| 拉伸断裂力 Fu_实测 | 10.5 N |
| 压缩外径 D | 0.8 mm |
| 压缩初始斜率 | 3.2 N/mm |
| 三点弯曲跨距 L | 30 mm |

**标定结果**：EA 修正 0.62、Kp 修正 0.40（v34 前）或 0.43（v34 后）、软化系数 c 0.27、粘接系数 η 0.50。

---

## 9.6 替代方案

无万能试验机时：挂砝码测拉伸，弹簧测力计加压测压缩。

---

## 9.7 保守默认值

| 系数 | 保守值 |
|---|---|
| EA 修正 | 0.6 |
| Kp 修正 | 0.4（薄壁） / 0.6（厚壁） |
| 粘接系数 η | 0.8 |
| 软化系数 c | 1.0 |
| 编织层压扁折减 | 0.7 |
| 跨距 L | 30 mm |

**此时工具可做相对比较，不能报绝对数值。**
    """)

with st.expander("10. 多方案对比", expanded=False):
    st.markdown("""
保存、载入、删除方案。方案是快照，保存后修改参数不会同步到已保存方案。

所有曲线图自动叠加显示所有方案，图例中标注每个方案的关键参数。
    """)

with st.expander("11. 导出功能", expanded=False):
    st.markdown("""
| 按钮 | 内容 | 格式 |
|---|---|---|
| 当前截面参数表 | 当前 x 位置所有层参数 | CSV |
| 沿长度曲线数据 | 200 个采样点的六条曲线 | CSV |
| 完整报告 | 多 sheet 完整报告 | Excel |

Excel 报告所有 sheet 和列名均为中文。
    """)

with st.expander("12. 常见问题", expanded=False):
    st.markdown("""
**Q1：算出来 Kp 太大？**
A：Kp 是线性小变形刚度，薄壁需乘 0.3~0.5，厚壁需乘 0.6~0.8。

**Q2：为什么改了模量，Fu 没变？**
A：Fu 只取决于抗拉强度。

**Q3：为什么弹簧圈层 Fu 有多个分量？**
A：弹簧圈层 Fu = 弹簧丝贡献 + 热熔填充贡献。

**Q4：为什么拉伸有控制层，但代码用整体极限？**
A：整体极限 Fu 是工程常用指标（拉断力）。起始屈服 Fu_y 是保守指标。

**Q5：编织层压扁折减怎么用？**
A：默认 1.0。已知编织层为网眼结构时可用 0.7~0.9。

**Q6：参数校验会检查什么？**
A：检查负值、内外半径倒置、模量强度非法、跨距过小、空值等。

**Q7：改了参数图表没更新？**
A：按一次 Enter，或点"🔄 强制刷新计算"。

**Q8：Excel 导出报错？**
A：需要安装 openpyxl。

**Q9：为什么强度分析里某层显示"— (σ≤0 跳过)"？**
A：该层抗拉强度设成了 0 或负。程序会从强度分析中排除它。

**Q10：v34 厚壁改进后为什么 Kp 变小了？**
A：有效几何常数 const_eff 随 t/R 增大而增大，Kp 相应降低。

**Q11：为什么在 data_editor 里改值要改两次才生效？**
A：v36 已修复。现在每次渲染前会把 data_editor 的缓存同步回 layer['data']。

**Q12：怎么做多段结构？**
A：在某个层里点"📋 复制最后一行"，会把最后一行复制一份追加到本层末尾，
新行的"起始位置"自动接续上一行的"结束位置"。然后改材料/半径等参数就行。

**Q13：v38 加固了什么？**
A：① 添加/删除层时清理所有层的会话状态；② safe_float 统一兜底；
③ compute_at_x 每层独立 try/except；④ 参数校验更严格。

**Q14：v40 修了什么？**
A：改了层名称后，侧边栏 expander 标题不同步。现在每次渲染前
先从 session_state 同步最新名称，标题与输入框保持一致。
    """)

with st.expander("13. 物理背景与局限", expanded=False):
    st.markdown("""
**理论模型**：多层同心圆管、完全粘接、材料线弹性、小变形、Timoshenko 薄环理论。

**v34 厚壁改进**：const_eff 随 t/R 连续变化，Kp 统一柔度叠加公式。

**v35~v39 稳定性修复**：
- 安全格式化函数
- data_editor 状态同步
- 复制/删除最后一行
- 全局 state 清理 + safe_float 加固
- 薄壁/厚壁判据修正（t/R_mid）
- Excel sheet 名清理

**v40 名称同步**：expander 标题实时反映最新层名称。

**主要简化**：忽略材料非线性、层间滑移、截面椭圆化（Brazier）、剪切变形、屈曲。

**薄壁 vs 厚壁的准确性**：
- 薄壁（t/R < 0.1）：EA 可信，EI 大曲率下高估，Fu_y / Fc 高估 2~3 倍，Kp 需 × 0.3~0.5
- 厚壁（t/R > 0.2）：EA/EI/Fu_y/My 较可信，Kp 需 × 0.6~0.8，Fc 仍有 15~30% 偏差

**适用范围**：相对比较、参数扫描、早期发现设计缺陷完全适用；预测绝对刚度值需实验标定。

**工具定位**：设计筛选工具，不是实验替代品。
    """)

# ============================================================
# 主区域剩余部分
# ============================================================

x_pos_safe = min(max(st.session_state.x_pos, 0.0), L_total)
x_pos = st.slider("Axial position x (mm)", min_value=0.0, max_value=L_total,
                  value=x_pos_safe, step=0.5)
st.session_state.x_pos = x_pos

all_schemes = []

xs, EA_arr, EI_arr, Kp_arr, Fu_arr, My_arr, Fc_arr = compute_along_length(
    structure, L_total, ea_correction, kp_correction, eta_bond, braid_crush_factor)
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
        'braid_crush_factor': braid_crush_factor,
    }
})

for s in saved_schemes:
    try:
        s_braid_crush = s.get('braid_crush_factor', 1.0)
        s_xs, s_EA, s_EI, s_Kp, s_Fu, s_My, s_Fc = compute_along_length(
            s['structure'], s['L_total'],
            s['ea_correction'], s['kp_correction'], s['eta_bond'],
            s_braid_crush)
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

layers = compute_at_x(structure, x_pos, eta_bond=eta_bond,
                       braid_crush_factor=braid_crush_factor)

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
st.markdown("## 一、刚度分析")
st.caption("刚度描述导管抵抗变形的能力。单位：EA (N)、EI (N·mm²)、Kp (N/mm)。")

if not layers:
    st.warning("该位置没有有效的层数据。请检查侧边栏参数或位置 x。")
else:
    EA, EI, Kp, EA_c, EI_c, Kp_c, model_used, thick_ratio = compute_stiffness(layers, ea_correction, kp_correction)

    c1, c2, c3 = st.columns(3)
    c1.metric("轴向刚度 EA (N)", f"{EA:.2f}")
    c2.metric("弯曲刚度 EI (N·mm²)", f"{EI:.2f}")
    c3.metric("抗压扁刚度 Kp (N/mm)", f"{Kp:.2f}")

    r0_disp = min(l['r_in'] for l in layers)
    rn_disp = max(l['r_out'] for l in layers)
    R_disp = (r0_disp + rn_disp) / 2
    tr_disp = (rn_disp - r0_disp) / R_disp if R_disp > 0 else 0.0
    const_eff_disp = compute_effective_const(tr_disp)
    const_thin_disp = np.pi / 4 - 2 / np.pi

    st.caption(
        f"当前截面 t/R = **{tr_disp:.3f}** | "
        f"有效几何常数 const_eff = **{const_eff_disp:.4f}** "
        f"（薄壁极限 {const_thin_disp:.4f}，比值 {const_eff_disp/const_thin_disp:.3f}）| "
        f"模型：**{model_used}**"
    )

    st.subheader("刚度沿长度分布")
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

    axes_s[0].set_ylabel('Axial Stiffness EA (N)')
    axes_s[0].set_xlabel('Axial position (mm)')
    axes_s[0].set_title('Axial Stiffness')
    axes_s[0].grid(True); axes_s[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[0].legend(loc='best', fontsize=8)

    axes_s[1].set_ylabel('Bending Stiffness EI (N·mm²)')
    axes_s[1].set_xlabel('Axial position (mm)')
    axes_s[1].set_title('Bending Stiffness')
    axes_s[1].grid(True); axes_s[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[1].legend(loc='best', fontsize=8)

    axes_s[2].set_ylabel('Crush Stiffness Kp (N/mm)')
    axes_s[2].set_xlabel('Axial position (mm)')
    axes_s[2].set_title(f'Crush Stiffness (correction × {kp_correction:.3f})')
    axes_s[2].grid(True); axes_s[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[2].legend(loc='best', fontsize=8)

    fig_s.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_s)

    st.subheader("抗压扁力-位移曲线（非线性）")
    st.caption(
        f"当前截面 Kp = {Kp:.3f} N/mm（已应用修正系数 {kp_correction:.3f}）。"
        f"软化系数 c = {softening_c:.2f}。"
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
            s_braid_crush = s_params.get('braid_crush_factor', 1.0)
            s_layers = compute_at_x(s_params['structure'], x_pos,
                                    eta_bond=s_params['eta_bond'],
                                    braid_crush_factor=s_braid_crush)
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

    label_lin = f"Current: Linear extrapolation (Kp={Kp:.2f} N/mm)"
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
            'ΔD / 外径': f"{dD_v / D_outer * 100:.1f}%" if D_outer > 0 else "—",
            '线性 F (N)': f"{F_lin:.4f}",
            '非线性 F (N)': f"{F_nl:.4f}",
            '软化幅度': f"-{delta_pct:.1f}%"
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    if len(all_schemes) > 1:
        st.markdown("---")
        st.subheader("📊 方案对比（当前截面）")
        compare_rows = []
        for sch in all_schemes:
            p = sch['params']
            try:
                s_braid_crush = p.get('braid_crush_factor', 1.0)
                if sch['is_current']:
                    s_layers_cmp = layers
                else:
                    s_layers_cmp = compute_at_x(p['structure'], x_pos,
                                                eta_bond=p['eta_bond'],
                                                braid_crush_factor=s_braid_crush)
                if s_layers_cmp:
                    s_EA_x, s_EI_x, s_Kp_x, _, _, _, _, _ = compute_stiffness(
                        s_layers_cmp, p['ea_correction'], p['kp_correction'])
                    s_Fu_x, _ = compute_axial_strength(s_layers_cmp)
                    s_Fu_y_x, _, _, _ = compute_axial_yield(s_layers_cmp, p['ea_correction'])
                    s_My_x, _, _, _ = compute_bending_yield(s_layers_cmp)
                    s_Fc_x, _, _, _ = compute_collapse_force(s_layers_cmp)
                    scheme_label = sch['name'] + (' (当前)' if sch['is_current'] else '')
                    compare_rows.append({
                        '方案': scheme_label,
                        'Kp 修正': f"{p['kp_correction']:.2f}",
                        '软化系数 c': f"{p['softening_c']:.2f}",
                        '粘接系数 η': f"{p['eta_bond']:.2f}",
                        '编织压扁折减': f"{s_braid_crush:.2f}",
                        '轴向刚度 EA (N)': f"{s_EA_x:.2f}",
                        '弯曲刚度 EI (N·mm²)': f"{s_EI_x:.2f}",
                        '抗压扁刚度 Kp (N/mm)': f"{s_Kp_x:.2f}",
                        '拉伸极限 Fu (N)': f"{s_Fu_x:.2f}",
                        '拉伸屈服 Fu_y (N)': f"{s_Fu_y_x:.2f}",
                        '弯曲屈服力矩 My (N·mm)': f"{s_My_x:.4f}",
                        '压扁屈服力 Fc (N)': f"{s_Fc_x:.2f}"
                    })
            except Exception:
                pass
        st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

    st.subheader("截面图")
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

    st.subheader("各层刚度贡献")
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

    st.markdown("**各层刚度贡献明细**")
    stiff_rows = []
    for i, l in enumerate(layers):
        ea_i_display = EA_c[i] * ea_correction
        ei_i_display = EI_c[i]
        kp_i_display = Kp_c[i]
        stiff_rows.append({
            "层": l['name'], "类型": l['type'],
            "EA 贡献 (N)": f"{ea_i_display:.4f}",
            "EA 占比 (%)": f"{ea_pct[i]:.2f}%",
            "EI 贡献 (N·mm²)": f"{ei_i_display:.4f}",
            "EI 占比 (%)": f"{ei_pct[i]:.2f}%",
            "Kp 贡献 (N/mm)": f"{kp_i_display:.4f}",
            "Kp 占比 (%)": f"{kp_pct[i]:.2f}%",
        })
    stiff_rows.append({
        "层": "合计", "类型": "",
        "EA 贡献 (N)": f"{EA:.4f}", "EA 占比 (%)": "100.00%",
        "EI 贡献 (N·mm²)": f"{EI:.4f}", "EI 占比 (%)": "100.00%",
        "Kp 贡献 (N/mm)": f"{Kp:.4f}", "Kp 占比 (%)": "100.00%",
    })
    st.dataframe(pd.DataFrame(stiff_rows), use_container_width=True, hide_index=True)

    filler_names = [l['name'] for l in layers if l.get('is_filler', False)]
    if filler_names:
        st.info(f"当前段缺失的层已自动用热熔材料填充：{', '.join(filler_names)}。")

    if thick_ratio < 0.08:
        st.info(f"壁厚/半径比 t/R = **{thick_ratio:.3f}** < 0.08（薄壁）。抗压扁模型：**{model_used}**。")
    elif thick_ratio < 0.15:
        st.warning(f"壁厚/半径比 t/R = **{thick_ratio:.3f}** ∈ [0.08, 0.15)（过渡区）。抗压扁模型：**{model_used}**。")
    elif thick_ratio < 0.5:
        st.info(f"壁厚/半径比 t/R = **{thick_ratio:.3f}** ∈ [0.15, 0.5)（厚壁）。抗压扁模型：**{model_used}**。")
    else:
        st.warning(f"壁厚/半径比 t/R = **{thick_ratio:.3f}** ≥ 0.5（极厚壁）。抗压扁模型：**{model_used}**。")

# ============================================================
# 第二部分：强度分析
# ============================================================
st.markdown("---")
st.markdown("## 二、强度分析")
st.caption(f"强度描述导管能承受的极限载荷。弯曲按三点弯曲换算，跨距 L = {L_span:.1f} mm。粘接系数 η = {eta_bond:.2f}。")

if layers:
    Fu, Fu_layer = compute_axial_strength(layers)
    Fu_y, ax_yield_ctrl, ax_yield_cands, ax_yield_contribs = compute_axial_yield(layers, ea_correction)
    My, bending_ctrl, bending_cands, bending_contribs = compute_bending_yield(layers)
    Fc, collapse_ctrl, collapse_cands, collapse_contribs = compute_collapse_force(layers)

    Fy_bending = 4 * My / L_span if L_span > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("拉伸极限 Fu (N)", f"{Fu:.2f}",
              help="各层贡献相加，拉断前的最大力")
    c2.metric("拉伸起始屈服 Fu_y (N)", f"{Fu_y:.2f}",
              help="第一层刚屈服时的整体拉力")
    c3.metric("弯曲屈服力矩 My (N·mm)", f"{My:.4f}")
    c4.metric("压扁屈服力 Fc (N)", f"{Fc:.2f}")

    ctrl_info = []
    if ax_yield_ctrl is not None:
        ctrl_info.append(f"**拉伸起始屈服控制层**：{ax_yield_ctrl}")
    if bending_ctrl is not None:
        ctrl_info.append(f"**弯曲屈服控制层**：{bending_ctrl}")
    if collapse_ctrl is not None:
        ctrl_info.append(f"**压扁屈服控制层**：{collapse_ctrl}")
    if ctrl_info:
        st.info("。".join(ctrl_info) + "。")
    else:
        st.warning("没有层满足强度分析条件（需 σ_uts > 0 且 E > 0）。")

    st.subheader("拉伸起始屈服 — 各层贡献")
    st.caption(
        "拉伸起始屈服指第一层表面达到抗拉强度时的整体拉力。"
        "σ_uts ≤ 0 的层不参与强度分析（在表中标注）。"
    )

    ax_rows = []
    for contrib in ax_yield_contribs:
        is_valid = contrib.get('is_valid', True)
        if is_valid:
            col_yield_force = f"{Fu_y:.4f}"
            col_flag = "★" if contrib['is_ctrl'] else ""
        else:
            col_yield_force = "—"
            col_flag = "— (σ≤0 跳过)"
        ax_rows.append({
            "层": contrib['layer'],
            "轴向模量 (MPa)": f"{contrib['E_z']:.1f}",
            "抗拉强度 (MPa)": f"{contrib['sigma_uts']:.1f}",
            "屈服应变 ε_y = σ/E": f"{contrib['eps_y']*100:.2f}%" if contrib['E_z'] > 0 and contrib['sigma_uts'] > 0 else "—",
            "该层屈服时整体拉力 (N)": col_yield_force,
            "整体屈服时该层承担拉力 (N)": f"{contrib['F_i']:.4f}",
            "占比 (%)": f"{contrib['pct']:.2f}%",
            "是否控制层": col_flag
        })
    st.dataframe(pd.DataFrame(ax_rows), use_container_width=True)

    st.subheader("弯曲屈服 — 各层贡献")
    st.caption("整体弯曲屈服力矩取所有有效层候选值的最小值。σ_uts ≤ 0 的层不参与强度分析。")

    b_ctrl_dict = {c['layer']: c for c in bending_cands}
    b_rows = []
    for contrib in bending_contribs:
        layer_name = contrib['layer']
        cand = b_ctrl_dict.get(layer_name, {})
        is_valid = contrib.get('is_valid', True)
        if is_valid:
            col_M_yield = f"{cand.get('M_y', 0):.4f}"
            col_flag = "★" if contrib['is_ctrl'] else ""
            col_Fy_3p = f"{4 * cand.get('M_y', 0) / L_span:.4f}" if L_span > 0 else "—"
        else:
            col_M_yield = "—"
            col_flag = "— (σ≤0 跳过)"
            col_Fy_3p = "—"
        b_rows.append({
            "层": layer_name,
            "轴向模量 (MPa)": f"{cand.get('E_z', 0):.1f}" if cand else "—",
            "外半径 (mm)": f"{cand.get('r_out', 0):.4f}" if cand else "—",
            "抗拉强度 (MPa)": f"{cand.get('sigma_uts', 0):.1f}",
            "该层屈服时整体弯矩 (N·mm)": col_M_yield,
            "整体屈服时该层承担弯矩 (N·mm)": f"{contrib['M_actual']:.4f}",
            "占比 (%)": f"{contrib['pct']:.2f}%",
            "是否控制层": col_flag,
            f"三点弯曲力 (N, L={L_span:.0f}mm)": col_Fy_3p
        })
    st.dataframe(pd.DataFrame(b_rows), use_container_width=True)

    st.subheader("压扁屈服 — 各层贡献")
    st.caption("整体压扁屈服力取所有有效层候选值的最小值。σ_uts ≤ 0 的层不参与强度分析。")

    c_ctrl_dict = {c['layer']: c for c in collapse_cands}
    c_rows = []
    for contrib in collapse_contribs:
        layer_name = contrib['layer']
        cand = c_ctrl_dict.get(layer_name, {})
        is_valid = contrib.get('is_valid', True)
        if is_valid:
            col_F_yield = f"{cand.get('F_c', 0):.4f}"
            col_flag = "★" if contrib['is_ctrl'] else ""
            E_theta_v = cand.get('E_theta', 0)
            sigma_v = cand.get('sigma_uts', 0)
            col_eps_y = f"{sigma_v / E_theta_v * 100:.2f}%" if E_theta_v > 0 and sigma_v > 0 else "—"
        else:
            col_F_yield = "—"
            col_flag = "— (σ≤0 跳过)"
            col_eps_y = "—"
        c_rows.append({
            "层": layer_name,
            "环向模量 (MPa)": f"{cand.get('E_theta', 0):.1f}" if cand else "—",
            "壁厚 (mm)": f"{cand.get('t', 0):.4f}" if cand else "—",
            "抗拉强度 (MPa)": f"{cand.get('sigma_uts', 0):.1f}",
            "屈服应变 ε_y = σ/E": col_eps_y,
            "该层屈服时整体受力 (N)": col_F_yield,
            "整体屈服时该层承担弯矩 (N·mm)": f"{contrib['M_actual']:.4f}",
            "占比 (%)": f"{contrib['pct']:.2f}%",
            "是否控制层": col_flag
        })
    st.dataframe(pd.DataFrame(c_rows), use_container_width=True)

    st.subheader("轴向拉力（整体极限） — 各层贡献")
    st.caption("弹簧圈/编织层 = 丝材/弹簧贡献 + 热熔填充贡献。整体极限 Fu = 各层贡献相加。")
    fu_rows = []
    for i, l in enumerate(layers):
        if l['type'] == '弹簧圈':
            method = "弹簧公式 + 热熔填充"
        elif l['type'] == '编织层':
            method = "丝材 + 热熔填充"
        elif l.get('is_filler', False):
            method = "填充层 (σ·A)"
        else:
            method = "σ·A"
        fu_rows.append({
            "层": l['name'], "类型": l['type'], "计算方法": method,
            "抗拉强度 (MPa)": f"{l['sigma_uts']:.1f}",
            "丝材/弹簧贡献 (N)": f"{l.get('Fu_fiber', 0.0):.4f}",
            "热熔填充贡献 (N)": f"{l.get('Fu_matrix', 0.0):.4f}",
            "合计 (N)": f"{Fu_layer[i]:.4f}"
        })
    st.dataframe(pd.DataFrame(fu_rows), use_container_width=True)

    st.subheader("强度沿长度分布")
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

    axes_t[0].set_ylabel('Axial Tensile Force Fu (N)')
    axes_t[0].set_xlabel('Axial position (mm)')
    axes_t[0].set_title('Max Axial Tensile Force')
    axes_t[0].grid(True); axes_t[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[0].legend(loc='best', fontsize=8)

    axes_t[1].set_ylabel('Bending Yield Moment My (N·mm)')
    axes_t[1].set_xlabel('Axial position (mm)')
    axes_t[1].set_title('Bending Yield Moment')
    axes_t[1].grid(True); axes_t[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[1].legend(loc='best', fontsize=8)

    axes_t[2].set_ylabel('Collapse Force Fc (N)')
    axes_t[2].set_xlabel('Axial position (mm)')
    axes_t[2].set_title('Collapse Force (weakest layer controls)')
    axes_t[2].grid(True); axes_t[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[2].legend(loc='best', fontsize=8)

    fig_t.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_t)

# ============================================================
# 参数明细表
# ============================================================
st.markdown("---")
st.subheader("当前位置层参数")
if layers:
    param_rows = []
    for l in layers:
        row = {
            "层": l['name'], "类型": l['type'],
            "内半径 (mm)": f"{l['r_in']:.4f}", "外半径 (mm)": f"{l['r_out']:.4f}",
            "轴向模量 (MPa)": f"{l['E_z']:.2f}", "环向模量 (MPa)": f"{l['E_theta']:.2f}",
            "抗拉强度 (MPa)": f"{l['sigma_uts']:.1f}"
        }
        row["丝材体积分数 (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        row["空隙体积分数 (%)"] = f"{l['V_void']*100:.2f}%" if l['V_void'] is not None else "—"
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
        '距远端位置 (mm)': xs,
        '轴向刚度 EA (N)': EA_arr,
        '弯曲刚度 EI (N·mm²)': EI_arr,
        '抗压扁刚度 Kp (N/mm)': Kp_arr,
        '轴向拉力 Fu (N)': Fu_arr,
        '弯曲屈服力矩 My (N·mm)': My_arr,
        '压扁屈服力 Fc (N)': Fc_arr
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
        try:
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                overview_data = {
                    '参数': ['导管总长度 (mm)', '当前轴向位置 (mm)', 'EA 修正系数',
                             'Kp 修正系数', '粘接系数 η', '三点弯曲跨距 (mm)',
                             '软化系数 c', '编织层压扁折减系数', '已保存方案数'],
                    '值': [L_total, x_pos, ea_correction, kp_correction, eta_bond, L_span,
                           softening_c, braid_crush_factor, len(saved_schemes)]
                }
                pd.DataFrame(overview_data).to_excel(writer, sheet_name='概览', index=False)

                if layers:
                    cur_metrics = {
                        '指标': ['轴向刚度 EA (N)', '弯曲刚度 EI (N·mm²)', '抗压扁刚度 Kp (N/mm)',
                                 '拉伸极限 Fu (N)', '拉伸起始屈服 Fu_y (N)',
                                 '弯曲屈服力矩 My (N·mm)', '压扁屈服力 Fc (N)',
                                 '壁厚半径比 t/R', '有效几何常数 const_eff'],
                        '值': [EA, EI, Kp, Fu, Fu_y, My, Fc, tr_disp, const_eff_disp]
                    }
                    pd.DataFrame(cur_metrics).to_excel(writer, sheet_name='当前截面指标', index=False)

                    stiff_export_rows = []
                    for i, l in enumerate(layers):
                        stiff_export_rows.append({
                            "层": l['name'],
                            "类型": l['type'],
                            "EA贡献_N": EA_c[i] * ea_correction,
                            "EA占比_%": ea_pct[i],
                            "EI贡献_Nmm2": EI_c[i],
                            "EI占比_%": ei_pct[i],
                            "Kp贡献_N_per_mm": Kp_c[i],
                            "Kp占比_%": kp_pct[i]
                        })
                    pd.DataFrame(stiff_export_rows).to_excel(
                        writer, sheet_name='刚度各层贡献', index=False)

                    ax_export_rows = []
                    for contrib in ax_yield_contribs:
                        is_valid = contrib.get('is_valid', True)
                        ax_export_rows.append({
                            "层": contrib['layer'],
                            "轴向模量_MPa": contrib['E_z'],
                            "抗拉强度_MPa": contrib['sigma_uts'],
                            "屈服应变_εy": contrib['eps_y'] if is_valid else None,
                            "整体屈服拉力_N": Fu_y if is_valid else None,
                            "该层承担拉力_N": contrib['F_i'],
                            "占比_%": contrib['pct'],
                            "是否控制层": "★" if contrib['is_ctrl'] else ("— (σ≤0 跳过)" if not is_valid else "")
                        })
                    pd.DataFrame(ax_export_rows).to_excel(
                        writer, sheet_name='拉伸起始屈服各层贡献', index=False)

                    bend_export_rows = []
                    for contrib in bending_contribs:
                        layer_name = contrib['layer']
                        cand = b_ctrl_dict.get(layer_name, {})
                        is_valid = contrib.get('is_valid', True)
                        bend_export_rows.append({
                            "层": layer_name,
                            "轴向模量_MPa": cand.get('E_z', None) if is_valid else None,
                            "外半径_mm": cand.get('r_out', None) if is_valid else None,
                            "抗拉强度_MPa": cand.get('sigma_uts', 0),
                            "该层屈服时整体弯矩_Nmm": cand.get('M_y', None) if is_valid else None,
                            "整体屈服时该层承担弯矩_Nmm": contrib['M_actual'],
                            "占比_%": contrib['pct'],
                            "是否控制层": "★" if contrib['is_ctrl'] else ("— (σ≤0 跳过)" if not is_valid else "")
                        })
                    pd.DataFrame(bend_export_rows).to_excel(
                        writer, sheet_name='弯曲屈服各层贡献', index=False)

                    coll_export_rows = []
                    for contrib in collapse_contribs:
                        layer_name = contrib['layer']
                        cand = c_ctrl_dict.get(layer_name, {})
                        is_valid = contrib.get('is_valid', True)
                        E_theta_v = cand.get('E_theta', 0)
                        sigma_v = cand.get('sigma_uts', 0)
                        coll_export_rows.append({
                            "层": layer_name,
                            "环向模量_MPa": E_theta_v if is_valid else None,
                            "壁厚_mm": cand.get('t', None) if is_valid else None,
                            "抗拉强度_MPa": sigma_v,
                            "屈服应变_%": (sigma_v / E_theta_v * 100) if (E_theta_v > 0 and is_valid) else None,
                            "该层屈服时整体受力_N": cand.get('F_c', None) if is_valid else None,
                            "整体屈服时该层承担弯矩_Nmm": contrib['M_actual'],
                            "占比_%": contrib['pct'],
                            "是否控制层": "★" if contrib['is_ctrl'] else ("— (σ≤0 跳过)" if not is_valid else "")
                        })
                    pd.DataFrame(coll_export_rows).to_excel(
                        writer, sheet_name='压扁屈服各层贡献', index=False)

                    fu_export_rows = []
                    for i, l in enumerate(layers):
                        fu_export_rows.append({
                            "层": l['name'],
                            "类型": l['type'],
                            "抗拉强度_MPa": l['sigma_uts'],
                            "丝材_弹簧贡献_N": l.get('Fu_fiber', 0.0),
                            "热熔填充贡献_N": l.get('Fu_matrix', 0.0),
                            "合计_N": Fu_layer[i]
                        })
                    pd.DataFrame(fu_export_rows).to_excel(
                        writer, sheet_name='轴向拉力各层贡献', index=False)

                    dD_export = np.linspace(0, 2.0, 200)
                    F_lin_export = Kp * dD_export
                    F_nl_export = compute_crush_force_nonlinear(Kp, D_outer, dD_export, softening_c)
                    fd_df = pd.DataFrame({
                        'ΔD 直径减小量 (mm)': dD_export,
                        '线性力 F (N)': F_lin_export,
                        '非线性力 F (N)': F_nl_export
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
                            s_braid_crush_e = p.get('braid_crush_factor', 1.0)
                            if sch['is_current']:
                                s_layers_export = layers
                            else:
                                s_layers_export = compute_at_x(p['structure'], x_pos,
                                                              eta_bond=p['eta_bond'],
                                                              braid_crush_factor=s_braid_crush_e)
                            if s_layers_export:
                                s_EA_x, s_EI_x, s_Kp_x, _, _, _, _, _ = compute_stiffness(
                                    s_layers_export, p['ea_correction'], p['kp_correction'])
                                s_Fu_x, _ = compute_axial_strength(s_layers_export)
                                s_Fu_y_x, _, _, _ = compute_axial_yield(s_layers_export, p['ea_correction'])
                                s_My_x, _, _, _ = compute_bending_yield(s_layers_export)
                                s_Fc_x, _, _, _ = compute_collapse_force(s_layers_export)
                                compare_rows_export.append({
                                    '方案': sch['name'] + (' (当前)' if sch['is_current'] else ''),
                                    'Kp 修正系数': p['kp_correction'],
                                    '软化系数 c': p['softening_c'],
                                    '粘接系数 η': p['eta_bond'],
                                    '编织层压扁折减': s_braid_crush_e,
                                    '轴向刚度 EA (N)': s_EA_x,
                                    '弯曲刚度 EI (N·mm²)': s_EI_x,
                                    '抗压扁刚度 Kp (N/mm)': s_Kp_x,
                                    '拉伸极限 Fu (N)': s_Fu_x,
                                    '拉伸起始屈服 Fu_y (N)': s_Fu_y_x,
                                    '弯曲屈服力矩 My (N·mm)': s_My_x,
                                    '压扁屈服力 Fc (N)': s_Fc_x
                                })
                        except Exception:
                            pass
                    if compare_rows_export:
                        pd.DataFrame(compare_rows_export).to_excel(
                            writer, sheet_name=f'方案对比_x{x_pos:.0f}mm', index=False)

                for i, layer in enumerate(structure):
                    sheet_name = sanitize_excel_sheet_name(f'层{i+1}_{layer["name"]}')
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
        except Exception as e:
            st.error(f"Excel 生成失败：{e}")
    else:
        st.button("📊 完整报告 (需 openpyxl)", disabled=True, key="dl_excel_disabled")
        st.caption("安装: pip install openpyxl")

st.caption("CSV 用 UTF-8 with BOM 编码，Excel 打开不会乱码。")
