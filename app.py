import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(page_title="微导管多层结构分析", layout="wide")

# ==================== 层类型定义 ====================
LAYER_TYPES = {
    '普通材料': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '弹性模量(MPa)', '抗拉强度(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.27, '外半径(mm)': 0.3048,
                    '弹性模量(MPa)': 100.0, '抗拉强度(MPa)': 106.2},
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
        'caption': '编织层：无编织层的段自动用热熔材料填充'
    },
    '弹簧圈': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '丝径(mm)', '螺距(mm)', '丝材模量(MPa)', '丝材抗拉强度(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                    '丝径(mm)': 0.0254, '螺距(mm)': 0.15,
                    '丝材模量(MPa)': 193000.0, '丝材抗拉强度(MPa)': 2200.0,
                    '原始基体体积分数': 0.0},
        'caption': '弹簧圈：抗拉力按弹簧拉伸公式；无弹簧圈的段自动用热熔材料填充'
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
                                '弹性模量(MPa)': 100.0, '抗拉强度(MPa)': 106.2}])},
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
CURRENT_VERSION = "v9_shared_yield"

if 'structure_version' not in st.session_state or st.session_state.structure_version != CURRENT_VERSION:
    st.session_state.structure = create_default_structure()
    st.session_state.structure_version = CURRENT_VERSION
    st.session_state.L_total = 30.0
    st.session_state.x_pos = 0.0
    st.session_state.ea_correction = 1.0
    st.session_state.kp_correction = 1.0
else:
    st.session_state.structure = normalize_structure(st.session_state.structure)

if 'L_total' not in st.session_state: st.session_state.L_total = 30.0
if 'x_pos' not in st.session_state: st.session_state.x_pos = 0.0
if 'ea_correction' not in st.session_state: st.session_state.ea_correction = 1.0
if 'kp_correction' not in st.session_state: st.session_state.kp_correction = 1.0

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

def find_hot_melt_E(structure, x):
    candidates = []
    for layer in structure:
        row = find_segment(layer['data'], x)
        if row is None:
            continue
        if layer['type'] == '普通材料':
            try:
                candidates.append((row['外半径(mm)'], row['弹性模量(MPa)']))
            except KeyError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1]

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
def compute_at_x(structure, x):
    hot_melt_E = find_hot_melt_E(structure, x)
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
            if ltype == '普通材料':
                E_z = row['弹性模量(MPa)']
                E_theta = E_z
                V_f = None
                sigma_uts = row.get('抗拉强度(MPa)', 0.0)
            elif ltype == '编织层':
                E_z, E_theta, V_f, V_void, alpha = compute_braid_moduli(row, hot_melt_E)
                sigma_uts = row.get('丝材抗拉强度(MPa)', 0.0)
            elif ltype == '弹簧圈':
                E_z, E_theta, V_f, V_void = compute_coil_moduli(row, hot_melt_E)
                sigma_uts = row.get('丝材抗拉强度(MPa)', 0.0)
                Fu_override = compute_coil_tensile_force(
                    sigma_uts, row['丝径(mm)'], row['螺距(mm)'],
                    row['内半径(mm)'], row['外半径(mm)'])
            else:
                continue
        except KeyError:
            continue
        layers.append({
            'name': layer['name'], 'type': ltype,
            'r_in': row['内半径(mm)'], 'r_out': row['外半径(mm)'],
            'E_z': E_z, 'E_theta': E_theta, 'V_f': V_f, 'V_void': V_void,
            'alpha': alpha, 'sigma_uts': float(sigma_uts),
            'Fu_override': Fu_override,
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
                               'sigma_uts': 15.0, 'Fu_override': None,
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
                               'sigma_uts': 15.0, 'Fu_override': None,
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

# ==================== 强度：弯曲屈服（共同变形） ====================
def compute_bending_yield(layers):
    """
    各层共同弯曲，曲率相同。谁最先达到抗拉强度，谁控制。
    曲率 κ = M / EI_total
    层 i 外表面应力 σ_i = E_z,i · κ · r_o,i
    令 σ_i = σ_uts,i：
        M_{y,i} = σ_uts,i · EI_total / (E_z,i · r_o,i)
    返回 (My, 控制层名, 所有候选)
    """
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

# ==================== 强度：压扁屈服（共同变形） ====================
def compute_collapse_force(layers):
    """
    各层共同承担压扁弯矩，曲率相同。
    M_max = C · F · R （单位轴向深度，C ≈ 0.318）
    κ = M_max / EI_theta_total
    层 i 表面应力 σ_i = E_theta,i · κ · (t_i/2)
    令 σ_i = σ_uts,i：
        F_{c,i} = σ_uts,i · EI_theta_total · 2 / (E_theta,i · C · R · t_i)
    返回 (Fc, 控制层名, 所有候选)
    """
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
def compute_along_length(structure, L_total, ea_corr=1.0, kp_corr=1.0, n=200):
    xs = np.linspace(0, L_total, n)
    EA_arr = np.zeros(n); EI_arr = np.zeros(n); Kp_arr = np.zeros(n)
    Fu_arr = np.zeros(n); My_arr = np.zeros(n); Fc_arr = np.zeros(n)
    for i, x in enumerate(xs):
        layers = compute_at_x(structure, x)
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
                key=f"data_{i}_v3"
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
    if st.button("🔄 强制刷新计算", type="primary"):
        st.rerun()

    if st.button("恢复示例数据"):
        for k in list(st.session_state.keys()):
            if k.startswith("data_") or k.startswith("name_") or k.startswith("type_"):
                del st.session_state[k]
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.session_state.ea_correction = 1.0
        st.session_state.kp_correction = 1.0
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层结构分析")

structure = st.session_state.structure
L_total = st.session_state.L_total
ea_correction = st.session_state.ea_correction
kp_correction = st.session_state.kp_correction

x_pos = st.slider("Axial position x (mm)", min_value=0.0, max_value=L_total,
                  value=st.session_state.x_pos, step=0.5)
st.session_state.x_pos = x_pos

xs, EA_arr, EI_arr, Kp_arr, Fu_arr, My_arr, Fc_arr = compute_along_length(
    structure, L_total, ea_correction, kp_correction)

layers = compute_at_x(structure, x_pos)

# ============================================================
# 第一部分：刚度分析
# ============================================================
st.markdown("## 一、Stiffness Analysis（刚度分析）")
st.caption("刚度描述导管抵抗变形的能力，是日常推送、过弯、抗压扁的核心性能指标。")

if not layers:
    st.warning("该位置没有层存在。")
else:
    EA, EI, Kp, EA_c, EI_c, Kp_c, model_used, thick_ratio = compute_stiffness(layers, ea_correction, kp_correction)

    c1, c2, c3 = st.columns(3)
    c1.metric("Axial Stiffness EA", f"{EA:.2f} N")
    c2.metric("Bending Stiffness EI", f"{EI:.2f} N·mm²")
    c3.metric("Crush Stiffness Kp", f"{Kp:.2f} N/mm")

    st.subheader("Stiffness along Length")
    fig_s, axes_s = plt.subplots(3, 1, figsize=(10, 12))
    fig_s.suptitle("Stiffness Distribution along Catheter Length", y=0.98, fontsize=13)

    axes_s[0].plot(xs, EA_arr, 'b-', linewidth=2)
    axes_s[0].set_ylabel('Axial Stiffness EA (N)')
    axes_s[0].set_title('Axial Stiffness')
    axes_s[0].grid(True); axes_s[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    axes_s[1].plot(xs, EI_arr, 'g-', linewidth=2)
    axes_s[1].set_ylabel('Bending Stiffness EI (N·mm²)')
    axes_s[1].set_title('Bending Stiffness')
    axes_s[1].grid(True); axes_s[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    axes_s[2].plot(xs, Kp_arr, 'r-', linewidth=2)
    axes_s[2].set_ylabel('Crush Stiffness Kp (N/mm)')
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
st.caption("强度描述导管能承受的极限载荷。弯曲和压扁采用「各层共同变形、最弱层先屈服」模型。")

if layers:
    Fu, Fu_layer = compute_axial_strength(layers)
    My, bending_ctrl, bending_cands = compute_bending_yield(layers)
    Fc, collapse_ctrl, collapse_cands = compute_collapse_force(layers)

    c1, c2, c3 = st.columns(3)
    c1.metric("Max Axial Tensile Force Fu", f"{Fu:.2f} N")
    c2.metric("Bending Yield Moment My", f"{My:.4f} N·mm")
    c3.metric("Collapse Force Fc", f"{Fc:.2f} N")

    # 控制层说明
    st.info(
        f"**弯曲屈服控制层**：{bending_ctrl}（该层外表面最先达到抗拉强度）。"
        f" **压扁屈服控制层**：{collapse_ctrl}（该层表面最先达到抗拉强度）。"
    )

    # 强度曲线
    st.subheader("Strength along Length")
    fig_t, axes_t = plt.subplots(3, 1, figsize=(10, 12))
    fig_t.suptitle("Strength Distribution along Catheter Length", y=0.98, fontsize=13)

    axes_t[0].plot(xs, Fu_arr, 'm-', linewidth=2)
    axes_t[0].set_ylabel('Axial Tensile Force Fu (N)')
    axes_t[0].set_title('Max Axial Tensile Force')
    axes_t[0].grid(True); axes_t[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    axes_t[1].plot(xs, My_arr, 'c-', linewidth=2)
    axes_t[1].set_ylabel('Bending Moment My (N·mm)')
    axes_t[1].set_title('Bending Yield Moment (weakest layer controls)')
    axes_t[1].grid(True); axes_t[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    axes_t[2].plot(xs, Fc_arr, 'y-', linewidth=2)
    axes_t[2].set_ylabel('Collapse Force Fc (N)')
    axes_t[2].set_xlabel('Axial position (mm)')
    axes_t[2].set_title('Collapse Force (weakest layer controls)')
    axes_t[2].grid(True); axes_t[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

    fig_t.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_t)

    # 弯曲屈服候选层明细
    st.subheader("Bending Yield — Candidate Layers")
    st.caption("每一层单独达到抗拉强度时，所需的整体弯矩。取最小值作为整体屈服力矩。")
    b_rows = []
    for c in bending_cands:
        b_rows.append({
            "Layer": c['layer'],
            "E_z (MPa)": f"{c['E_z']:.1f}",
            "r_out (mm)": f"{c['r_out']:.4f}",
            "σ_uts (MPa)": f"{c['sigma_uts']:.1f}",
            "M_y (N·mm)": f"{c['M_y']:.4f}"
        })
    st.dataframe(pd.DataFrame(b_rows), use_container_width=True)

    # 压扁屈服候选层明细
    st.subheader("Collapse — Candidate Layers")
    st.caption("每一层单独达到抗拉强度时，所需的整体压扁力。取最小值作为整体压扁屈服力。")
    c_rows = []
    for c in collapse_cands:
        c_rows.append({
            "Layer": c['layer'],
            "E_theta (MPa)": f"{c['E_theta']:.1f}",
            "t (mm)": f"{c['t']:.4f}",
            "σ_uts (MPa)": f"{c['sigma_uts']:.1f}",
            "F_c (N)": f"{c['F_c']:.4f}"
        })
    st.dataframe(pd.DataFrame(c_rows), use_container_width=True)

    # 轴向拉力贡献
    st.subheader("Axial Tensile — Layer Contributions")
    fu_rows = []
    for i, l in enumerate(layers):
        method = "Spring formula" if l.get('Fu_override') is not None else "σ·A·Vf"
        fu_rows.append({
            "Layer": l['name'], "Type": l['type'], "Method": method,
            "UTS (MPa)": f"{l['sigma_uts']:.1f}",
            "Fu (N)": f"{Fu_layer[i]:.4f}"
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
    st.dataframe(pd.DataFrame(param_rows), use_container_width=True)
