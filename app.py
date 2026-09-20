import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(page_title="微导管多层结构刚度与强度分析", layout="wide")

# ==================== 层类型定义 ====================
LAYER_TYPES = {
    '普通材料': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)', 
                    '弹性模量(MPa)', '屈服强度(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.27, '外半径(mm)': 0.3048, 
                    '弹性模量(MPa)': 100.0, '屈服强度(MPa)': 80.5},
        'caption': '普通材料：各向同性，E_z = E_θ'
    },
    '编织层': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '扁丝宽度(mm)', '扁丝厚度(mm)', '股数', '每束根数',
                    '每英寸交叉数', '丝材模量(MPa)', '丝材屈服强度(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                    '扁丝宽度(mm)': 0.05, '扁丝厚度(mm)': 0.02,
                    '股数': 16, '每束根数': 1, '每英寸交叉数': 80,
                    '丝材模量(MPa)': 193000.0, '丝材屈服强度(MPa)': 300.0, 
                    '原始基体体积分数': 0.0},
        'caption': '编织层：无编织层的段自动用热熔材料填充'
    },
    '弹簧圈': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '丝径(mm)', '螺距(mm)', '丝材模量(MPa)', '丝材屈服强度(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                    '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                    '丝径(mm)': 0.0254, '螺距(mm)': 7.75,
                    '丝材模量(MPa)': 193000.0, '丝材屈服强度(MPa)': 300.0, 
                    '原始基体体积分数': 0.0},
        'caption': '弹簧圈：无弹簧圈的段自动用热熔材料填充'
    },
}

def make_default_layer(layer_type, L_total=30, r_in=0.27, r_out=0.3048):
    d = LAYER_TYPES[layer_type]['default'].copy()
    d['结束位置(mm)'] = L_total
    d['内半径(mm)'] = r_in
    d['外半径(mm)'] = r_out
    return pd.DataFrame([d])

def create_default_structure(L_total=30):
    """按照用户截图更新默认结构"""
    return [
        {'name': 'Hot Melt', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                                '内半径(mm)': 0.33, '外半径(mm)': 0.4,
                                '弹性模量(MPa)': 12.0, '屈服强度(MPa)': 10.0}])},
        {'name': 'Braid', 'type': '弹簧圈',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                                '内半径(mm)': 0.3048, '外半径(mm)': 0.33,
                                '丝径(mm)': 0.0254, '螺距(mm)': 7.75,
                                '丝材模量(MPa)': 193000.0, '丝材屈服强度(MPa)': 300.0, 
                                '原始基体体积分数': 0.0}])},
        {'name': 'Coil', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': 30.0,
                                '内半径(mm)': 0.27, '外半径(mm)': 0.3048,
                                '弹性模量(MPa)': 100.0, '屈服强度(MPa)': 80.5}])},
    ]

def normalize_structure(structure):
    """健壮版：处理旧缓存中的非 DataFrame 数据，并补齐列"""
    for layer in structure:
        if not isinstance(layer, dict) or 'data' not in layer:
            continue
        df = layer['data']
        # 1. 强制转换为 DataFrame
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
        # 2. 空 DataFrame 用默认值填充
        if df.empty:
            layer['data'] = make_default_layer(layer.get('type', '普通材料'))
            continue
        # 3. 补齐列名
        expected_cols = LAYER_TYPES[layer['type']]['columns']
        if list(df.columns) != expected_cols:
            for col in expected_cols:
                if col not in df.columns:
                    if '屈服强度' in col:
                        df[col] = 10.0 if layer['type'] == '普通材料' else 300.0
                    else:
                        df[col] = LAYER_TYPES[layer['type']]['default'].get(col, 0.0)
            layer['data'] = df[expected_cols]
    return structure

# ==================== 会话状态与版本重置 ====================
CURRENT_VERSION = "v2"   # 改结构时递增

if 'structure_version' not in st.session_state or st.session_state.structure_version != CURRENT_VERSION:
    st.session_state.structure = create_default_structure()
    st.session_state.structure_version = CURRENT_VERSION
    st.session_state.L_total = 30.0
    st.session_state.x_pos = 0.0
    st.session_state.ea_correction = 0.5
    st.session_state.kp_correction = 1.0
else:
    st.session_state.structure = normalize_structure(st.session_state.structure)

if 'L_total' not in st.session_state: st.session_state.L_total = 30.0
if 'x_pos' not in st.session_state: st.session_state.x_pos = 0.0
if 'ea_correction' not in st.session_state: st.session_state.ea_correction = 0.5
if 'kp_correction' not in st.session_state: st.session_state.kp_correction = 1.0

# ==================== 回调函数 ====================
def sync_editor_data(layer_idx, editor_key):
    if editor_key in st.session_state:
        if 0 <= layer_idx < len(st.session_state.structure):
            st.session_state.structure[layer_idx]['data'] = st.session_state[editor_key]

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
                r_out = row['外半径(mm)']
                E = row['弹性模量(MPa)']
                candidates.append((r_out, E))
            except KeyError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1]

# ==================== 参考半径提取 ====================
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
                r_in = row['内半径(mm)']
                r_out = row['外半径(mm)']
                refs.append((r_in, r_out))
            except Exception:
                continue
    if not refs:
        return None
    return (float(np.median([r[0] for r in refs])), float(np.median([r[1] for r in refs])))

# ==================== 编织角自动计算 ====================
def compute_braid_angle(r_in, r_out, PPI, N_strands):
    D_mid = r_in + r_out
    if N_strands <= 0 or D_mid <= 0:
        return 45.0
    val = np.pi * D_mid * PPI / (25.4 * N_strands)
    return np.degrees(np.arctan(val))

# ==================== 编织层各向异性模量与空隙计算 ====================
def compute_braid_moduli(row, E_hm):
    if E_hm is None:
        E_hm = 0.0
    w = row['扁丝宽度(mm)']; t = row['扁丝厚度(mm)']
    N = row['股数']; n_s = row['每束根数']
    PPI = row['每英寸交叉数']; E_f = row['丝材模量(MPa)']
    r_in, r_out = row['内半径(mm)'], row['外半径(mm)']
    V_matrix = row.get('原始基体体积分数', 0.0)

    alpha = compute_braid_angle(r_in, r_out, PPI, N)
    alpha_rad = np.radians(alpha)

    denom = np.pi * (r_out**2 - r_in**2) * np.cos(alpha_rad)
    if denom > 0:
        V_f = min(1.0, 2 * N * n_s * w * t / denom)
    else:
        V_f = 0.0
    V_void = max(0.0, 1.0 - V_f - V_matrix)
    if V_void + V_matrix > 0:
        E_m_eff = E_hm * V_void / (V_void + V_matrix)
    else:
        E_m_eff = 0.0

    E_z = E_f * V_f * (np.cos(alpha_rad)**4) + E_m_eff * (1 - V_f)
    E_theta = E_f * V_f * (np.sin(alpha_rad)**4) + E_m_eff * (1 - V_f)
    return E_z, E_theta, V_f, V_void, alpha

# ==================== 弹簧圈各向异性模量与空隙计算 ====================
def compute_coil_moduli(row, E_hm):
    if E_hm is None:
        E_hm = 0.0
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
    if V_void + V_matrix > 0:
        E_m_eff = E_hm * V_void / (V_void + V_matrix)
    else:
        E_m_eff = 0.0

    if D > 0 and A > 0 and pitch > 0:
        E_spring_axial = G * d**4 * pitch / (8 * D**3 * A)
    else:
        E_spring_axial = 0.0
    E_z = E_spring_axial + E_m_eff * (1 - V_spring)
    E_theta = E_f * V_spring + E_m_eff * (1 - V_spring)
    return E_z, E_theta, V_spring, V_void

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
            if ltype == '普通材料':
                E_z = row['弹性模量(MPa)']
                E_theta = E_z
                V_f = None
                sigma_y = row.get('屈服强度(MPa)', 0.0)
            elif ltype == '编织层':
                E_z, E_theta, V_f, V_void, alpha = compute_braid_moduli(row, hot_melt_E)
                sigma_y = row.get('丝材屈服强度(MPa)', 0.0)
            elif ltype == '弹簧圈':
                E_z, E_theta, V_f, V_void = compute_coil_moduli(row, hot_melt_E)
                sigma_y = row.get('丝材屈服强度(MPa)', 0.0)
            else:
                continue
        except KeyError:
            continue
        layers.append({
            'name': layer['name'], 'type': ltype,
            'r_in': row['内半径(mm)'], 'r_out': row['外半径(mm)'],
            'E_z': E_z, 'E_theta': E_theta, 'V_f': V_f, 'V_void': V_void, 
            'alpha': alpha, 'sigma_y': sigma_y, 'layer_idx': idx, 'is_filler': False
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
                layers.append({
                    'name': 'Hot Melt (braid filler)', 'type': '普通材料',
                    'r_in': r_in_ref, 'r_out': r_out_ref,
                    'E_z': hot_melt_E, 'E_theta': hot_melt_E,
                    'V_f': None, 'V_void': None, 'alpha': None, 'sigma_y': 10.0,
                    'layer_idx': -2, 'is_filler': True
                })

    if not has_coil_here:
        coil_ref = get_reference_radius(structure, '弹簧圈')
        if coil_ref is not None and hot_melt_E is not None:
            r_in_ref, r_out_ref = coil_ref
            if not is_occupied(r_in_ref, r_out_ref):
                layers.append({
                    'name': 'Hot Melt (coil filler)', 'type': '普通材料',
                    'r_in': r_in_ref, 'r_out': r_out_ref,
                    'E_z': hot_melt_E, 'E_theta': hot_melt_E,
                    'V_f': None, 'V_void': None, 'alpha': None, 'sigma_y': 10.0,
                    'layer_idx': -1, 'is_filler': True
                })

    layers.sort(key=lambda l: -l['r_out'])
    return layers

# ==================== 单层管壁刚度 ====================
def compute_wall_bending_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    if t <= 0: return 0.0
    if r_in <= 1e-9 or r_in / r_out < 0.5:
        return E_theta * t**3 / 12
    r_n = t / np.log(r_out / r_in)
    R_layer = (r_out + r_in) / 2
    e = R_layer - r_n
    return E_theta * t * e * r_n

def compute_wall_axial_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    if t <= 0: return 0.0
    return E_theta * t

# ==================== 刚度与屈服力计算 ====================
def compute_stiffness(layers, correction_factor=1.0):
    EA_c, EI_c = [], []
    EI_theta_bend_c, EA_theta_c = [], []
    F_yield = 0.0

    for l in layers:
        r_in, r_out = l['r_in'], l['r_out']
        E_z = l['E_z']; E_theta = l.get('E_theta', E_z)
        A_i = np.pi * (r_out**2 - r_in**2)
        
        EA_c.append(E_z * A_i)
        EI_c.append((np.pi / 4) * E_z * (r_out**4 - r_in**4))
        EI_theta_bend_c.append(compute_wall_bending_stiffness(E_theta, r_in, r_out))
        EA_theta_c.append(compute_wall_axial_stiffness(E_theta, r_in, r_out))
        
        V_f = l.get('V_f')
        if V_f is None: V_f = 1.0
        F_yield += l.get('sigma_y', 0.0) * A_i * V_f

    EA = sum(EA_c) * correction_factor
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

        Kp = Kp_raw * correction_factor
        Kp_c = [ei / EI_theta_bend * Kp for ei in EI_theta_bend_c] if EI_theta_bend > 0 else [0.0]*len(layers)
    else:
        Kp = 0.0; Kp_c = []; model_used = "N/A"; thick_ratio = 0.0

    return EA, EI, Kp, F_yield, EA_c, EI_c, Kp_c, model_used, thick_ratio

def compute_along_length(structure, L_total, ea_corr=1.0, kp_corr=1.0, n=300):
    xs = np.linspace(0, L_total, n)
    EA_arr = np.zeros(n); EI_arr = np.zeros(n); Kp_arr = np.zeros(n); Fy_arr = np.zeros(n)
    for i, x in enumerate(xs):
        layers = compute_at_x(structure, x)
        EA, EI, Kp, Fy, _, _, _, _, _ = compute_stiffness(layers, kp_corr)
        EA_arr[i] = EA; EI_arr[i] = EI; Kp_arr[i] = Kp; Fy_arr[i] = Fy
    return xs, EA_arr, EI_arr, Kp_arr, Fy_arr

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
                layer['name'] = st.text_input("名称（图表中显示）", value=layer['name'], key=f"name_{i}")
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
            
            st.data_editor(
                layer['data'], 
                num_rows="dynamic", 
                use_container_width=True, 
                key=f"data_{i}",
                on_change=sync_editor_data,
                args=(i, f"data_{i}")
            )

    st.markdown("---")
    st.markdown("**刚度与强度修正系数**")
    ea_correction = st.number_input("轴向刚度 EA 修正系数（实验标定）", 
                                    min_value=0.01, max_value=2.0, 
                                    value=float(st.session_state.ea_correction), 
                                    step=0.05, format="%.2f", key="ea_corr_input")
    st.session_state.ea_correction = ea_correction
    
    kp_correction = st.number_input("抗压扁刚度 Kp 修正系数（实验标定）", 
                                    min_value=0.01, max_value=10.0, 
                                    value=float(st.session_state.kp_correction), 
                                    step=0.01, format="%.3f", key="kp_corr_input")
    st.session_state.kp_correction = kp_correction
    
    st.caption("默认 EA 修正 0.5（考虑层间滑移与尺寸效应），Kp 修正 1.0。")

    st.markdown("---")
    if st.button("🔄 强制刷新计算并更新图表", type="primary"):
        st.rerun()

    if st.button("恢复示例数据"):
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.session_state.ea_correction = 0.5
        st.session_state.kp_correction = 1.0
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层结构刚度与屈服强度分析")

structure = st.session_state.structure
L_total = st.session_state.L_total
ea_correction = st.session_state.ea_correction
kp_correction = st.session_state.kp_correction

x_pos = st.slider("Axial position x (mm)", min_value=0.0, max_value=L_total, value=st.session_state.x_pos, step=0.5)
st.session_state.x_pos = x_pos

xs, EA_arr, EI_arr, Kp_arr, Fy_arr = compute_along_length(structure, L_total, ea_correction, kp_correction)

st.subheader("Stiffness & Yield Force along Length")
fig, axes = plt.subplots(4, 1, figsize=(10, 16))
fig.suptitle("Stiffness and Yield Force Distribution", y=0.98, fontsize=14)

axes[0].plot(xs, EA_arr, 'b-', linewidth=2)
axes[0].set_ylabel('Axial Stiffness EA (N)')
axes[0].set_title('Axial Stiffness (corrected)')
axes[0].grid(True); axes[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[1].plot(xs, Fy_arr, 'm-', linewidth=2)
axes[1].set_ylabel('Axial Yield Force Fy (N)')
axes[1].set_title('Max Axial Yield Force (Theoretical)')
axes[1].grid(True); axes[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[2].plot(xs, EI_arr, 'g-', linewidth=2)
axes[2].set_ylabel('Bending Stiffness EI (N·mm²)')
axes[2].set_title('Bending Stiffness')
axes[2].grid(True); axes[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[3].plot(xs, Kp_arr, 'r-', linewidth=2)
axes[3].set_ylabel('Crush Stiffness Kp (N/mm)')
axes[3].set_xlabel('Axial position (mm)')
axes[3].set_title(f'Crush Stiffness (correction × {kp_correction:.3f})')
axes[3].grid(True); axes[3].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

fig.tight_layout(rect=[0, 0, 1, 0.96])
st.pyplot(fig)

st.subheader(f"Cross-section Analysis at x = {x_pos:.1f} mm")
layers = compute_at_x(structure, x_pos)

if not layers:
    st.warning("该位置没有层存在。")
else:
    EA, EI, Kp, Fy, EA_c, EI_c, Kp_c, model_used, thick_ratio = compute_stiffness(layers, kp_correction)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Axial Stiffness EA", f"{EA:.2f} N")
    c2.metric("Bending Stiffness EI", f"{EI:.2f} N·mm²")
    c3.metric("Crush Stiffness Kp", f"{Kp:.2f} N/mm")
    c4.metric("Max Axial Yield Force Fy", f"{Fy:.2f} N")

    filler_names = [l['name'] for l in layers if l.get('is_filler', False)]
    if filler_names:
        st.info(f"当前段缺失的层已自动用热熔材料填充：{', '.join(filler_names)}。")

    if thick_ratio < 0.1:
        st.info(f"壁厚/半径比 = **{thick_ratio:.3f}** < 0.1（薄壁）。抗压扁模型：**{model_used}**。")
    elif thick_ratio < 0.5:
        st.warning(f"壁厚/半径比 = **{thick_ratio:.3f}** ∈ [0.1, 0.5)（厚壁）。抗压扁模型：**{model_used}**。")
    else:
        st.error(f"壁厚/半径比 = **{thick_ratio:.3f}** ≥ 0.5（极厚壁）。抗压扁模型：**{model_used}**。")

    st.subheader("Cross-section View")
    fig2, ax2 = plt.subplots(figsize=(5, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(layers), 1)))
    for i, l in enumerate(layers):
        r_in, r_out = l['r_in'], l['r_out']
        ax2.add_patch(plt.Circle((0, 0), r_out, color=colors[i], alpha=0.6))
        ax2.add_patch(plt.Circle((0, 0), r_in, color='white', fill=True))
        if l['type'] == '编织层':
            ax2.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360, width=r_out - r_in, fill=False, hatch='///', edgecolor='none'))
        elif l['type'] == '弹簧圈':
            ax2.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360, width=r_out - r_in, fill=False, hatch='xxx', edgecolor='none'))
        elif l.get('is_filler', False):
            ax2.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360, width=r_out - r_in, fill=False, hatch='...', edgecolor='none'))

    inner_r = min(l['r_in'] for l in layers)
    if inner_r > 0:
        ax2.add_patch(plt.Circle((0, 0), inner_r, color='white', fill=True))
    R_max = max(l['r_out'] for l in layers)
    ax2.set_xlim(-R_max*1.2, R_max*1.2); ax2.set_ylim(-R_max*1.2, R_max*1.2)
    ax2.set_aspect('equal'); ax2.axis('off')
    st.pyplot(fig2)

    st.subheader("Layer Contributions to EA (%)")
    labels = [l['name'] for l in layers]
    ea_pct = [v/EA*100 if EA > 0 else 0 for v in EA_c]
    
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    ax3.bar(labels, ea_pct, color=colors[:len(layers)])
    ax3.set_ylabel('Contribution to EA (%)')
    ax3.grid(axis='y', linestyle='--', alpha=0.6)
    st.pyplot(fig3)

    st.subheader("Layer Parameters at This Position")
    param_rows = []
    for l in layers:
        row = {
            "Layer": l['name'], "Type": l['type'],
            "r_in (mm)": l['r_in'], "r_out (mm)": l['r_out'],
            "E_z (MPa)": f"{l['E_z']:.2f}", "E_theta (MPa)": f"{l['E_theta']:.2f}",
            "Yield Strength (MPa)": f"{l.get('sigma_y', 0):.1f}"
        }
        row["V_f (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        row["V_void (%)"] = f"{l['V_void']*100:.2f}%" if l['V_void'] is not None else "—"
        param_rows.append(row)
    st.dataframe(pd.DataFrame(param_rows), use_container_width=True)
