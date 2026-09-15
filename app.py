import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(page_title="微导管多层结构刚度分析", layout="wide")

# ==================== 层类型定义 ====================
LAYER_TYPES = {
    '普通材料': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)', '弹性模量(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 350.0,
                    '内半径(mm)': 0.40, '外半径(mm)': 0.45, '弹性模量(MPa)': 500.0},
        'caption': '普通材料：各向同性，E_z = E_θ'
    },
    '编织层': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '扁丝宽度(mm)', '扁丝厚度(mm)', '股数', '每束根数',
                    '每英寸交叉数', '丝材模量(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 350.0,
                    '内半径(mm)': 0.45, '外半径(mm)': 0.55,
                    '扁丝宽度(mm)': 0.05, '扁丝厚度(mm)': 0.02,
                    '股数': 16, '每束根数': 1, '每英寸交叉数': 80,
                    '丝材模量(MPa)': 200000.0, '原始基体体积分数': 0.0},
        'caption': '编织层：编织角自动计算；E_z 用于轴向/弯曲，E_θ 用于抗压扁'
    },
    '弹簧圈': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '丝径(mm)', '螺距(mm)', '丝材模量(MPa)', '原始基体体积分数'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 350.0,
                    '内半径(mm)': 0.42, '外半径(mm)': 0.45,
                    '丝径(mm)': 0.02, '螺距(mm)': 0.10,
                    '丝材模量(MPa)': 200000.0, '原始基体体积分数': 0.0},
        'caption': '弹簧圈：E_z 用弹簧模型，E_θ 用丝材体积分数'
    },
}

def make_default_layer(layer_type, L_total=350, r_in=0.4, r_out=0.45):
    d = LAYER_TYPES[layer_type]['default'].copy()
    d['结束位置(mm)'] = L_total
    d['内半径(mm)'] = r_in
    d['外半径(mm)'] = r_out
    return pd.DataFrame([d])

def create_default_structure(L_total=350):
    return [
        {'name': 'Hot Melt', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.55, '外半径(mm)': 0.60,
                                '弹性模量(MPa)': 50.0}])},
        {'name': 'Braid', 'type': '编织层',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.45, '外半径(mm)': 0.55,
                                '扁丝宽度(mm)': 0.05, '扁丝厚度(mm)': 0.02,
                                '股数': 16, '每束根数': 1, '每英寸交叉数': 80,
                                '丝材模量(MPa)': 200000.0, '原始基体体积分数': 0.0}])},
        {'name': 'Coil', 'type': '弹簧圈',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.42, '外半径(mm)': 0.45,
                                '丝径(mm)': 0.02, '螺距(mm)': 0.10,
                                '丝材模量(MPa)': 200000.0, '原始基体体积分数': 0.0}])},
        {'name': 'PTFE', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.40, '外半径(mm)': 0.42,
                                '弹性模量(MPa)': 500.0}])},
    ]

def normalize_structure(structure):
    for layer in structure:
        expected_cols = LAYER_TYPES[layer['type']]['columns']
        df = layer['data']
        if list(df.columns) != expected_cols:
            old = df.iloc[0].to_dict() if len(df) > 0 else {}
            r_in = old.get('内半径(mm)', old.get('r_in', 0.4))
            r_out = old.get('外半径(mm)', old.get('r_out', 0.45))
            start = old.get('起始位置(mm)', old.get('start_x', 0.0))
            end = old.get('结束位置(mm)', old.get('end_x', 350.0))
            new_df = make_default_layer(layer['type'], end, r_in, r_out)
            new_df.loc[0, '起始位置(mm)'] = start
            layer['data'] = new_df
    return structure

# ==================== 半径校验 ====================
def validate_structure(structure, L_total):
    errors = []
    warnings = []

    for i, layer in enumerate(structure):
        df = layer['data']
        name = layer['name']
        if df is None or df.empty:
            errors.append(f"第 {i+1} 层（{name}）没有任何分段数据")
            continue

        for j, row in df.iterrows():
            try:
                start = row['起始位置(mm)']
                end = row['结束位置(mm)']
                r_in = row['内半径(mm)']
                r_out = row['外半径(mm)']
            except KeyError:
                errors.append(f"第 {i+1} 层（{name}）分段 {j+1} 缺少必要列")
                continue

            if start < 0:
                errors.append(f"第 {i+1} 层（{name}）分段 {j+1} 起始位置为负（{start}）")
            if end <= start:
                errors.append(f"第 {i+1} 层（{name}）分段 {j+1} 结束位置不大于起始位置（{start} → {end}）")
            if end > L_total + 1e-6:
                warnings.append(f"第 {i+1} 层（{name}）分段 {j+1} 结束位置 {end} 超出导管总长 {L_total}")

            if r_in < 0:
                errors.append(f"第 {i+1} 层（{name}）分段 {j+1} 内半径为负（{r_in}）")
            if r_out < 0:
                errors.append(f"第 {i+1} 层（{name}）分段 {j+1} 外半径为负（{r_out}）")
            if r_out <= r_in:
                errors.append(f"第 {i+1} 层（{name}）分段 {j+1} 外半径不大于内半径（{r_in} → {r_out}）")

    sample_points = np.linspace(0, L_total, 100)
    for x in sample_points:
        active = []
        for i, layer in enumerate(structure):
            row = find_segment(layer['data'], x)
            if row is not None:
                active.append((i, layer['name'], row['内半径(mm)'], row['外半径(mm)']))

        if not active:
            continue

        active_sorted = sorted(active, key=lambda a: a[2])
        for k in range(len(active_sorted) - 1):
            i1, name1, ri1, ro1 = active_sorted[k]
            i2, name2, ri2, ro2 = active_sorted[k + 1]

            gap = ri2 - ro1
            if gap > 0.005:
                warnings.append(
                    f"x = {x:.1f} mm 处：第 {i1+1} 层（{name1}）外半径 {ro1:.3f} 与 "
                    f"第 {i2+1} 层（{name2}）内半径 {ri2:.3f} 之间存在间隙 {gap:.3f} mm"
                )
            elif gap < -0.005:
                warnings.append(
                    f"x = {x:.1f} mm 处：第 {i1+1} 层（{name1}）外半径 {ro1:.3f} 与 "
                    f"第 {i2+1} 层（{name2}）内半径 {ri2:.3f} 之间存在重叠 {-gap:.3f} mm"
                )

    warnings = list(dict.fromkeys(warnings))
    errors = list(dict.fromkeys(errors))
    return errors, warnings

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
    for idx, layer in enumerate(structure):
        row = find_segment(layer['data'], x)
        if row is None:
            continue
        ltype = layer['type']
        try:
            alpha = None
            V_void = None
            if ltype == '普通材料':
                E_z = row['弹性模量(MPa)']
                E_theta = E_z
                V_f = None
            elif ltype == '编织层':
                E_z, E_theta, V_f, V_void, alpha = compute_braid_moduli(row, hot_melt_E)
            elif ltype == '弹簧圈':
                E_z, E_theta, V_f, V_void = compute_coil_moduli(row, hot_melt_E)
            else:
                continue
        except KeyError:
            continue
        layers.append({
            'name': layer['name'],
            'type': ltype,
            'r_in': row['内半径(mm)'],
            'r_out': row['外半径(mm)'],
            'E_z': E_z,
            'E_theta': E_theta,
            'V_f': V_f,
            'V_void': V_void,
            'alpha': alpha,
            'layer_idx': idx
        })
    layers.sort(key=lambda l: -l['r_out'])
    return layers

# ==================== 单层管壁刚度（曲梁修正） ====================
def compute_wall_bending_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    if t <= 0:
        return 0.0
    if r_in <= 1e-9 or r_in / r_out < 0.5:
        return E_theta * t**3 / 12
    r_n = t / np.log(r_out / r_in)
    R_layer = (r_out + r_in) / 2
    e = R_layer - r_n
    return E_theta * t * e * r_n

def compute_wall_axial_stiffness(E_theta, r_in, r_out):
    t = r_out - r_in
    if t <= 0:
        return 0.0
    return E_theta * t

# ==================== 刚度计算（自适应模型） ====================
def compute_stiffness(layers, correction_factor=1.0):
    EA_c, EI_c = [], []
    EI_theta_bend_c, EA_theta_c = [], []

    for l in layers:
        r_in, r_out = l['r_in'], l['r_out']
        E_z = l['E_z']
        E_theta = l.get('E_theta', E_z)

        EA_c.append(np.pi * E_z * (r_out**2 - r_in**2))
        EI_c.append((np.pi / 4) * E_z * (r_out**4 - r_in**4))
        EI_theta_bend_c.append(compute_wall_bending_stiffness(E_theta, r_in, r_out))
        EA_theta_c.append(compute_wall_axial_stiffness(E_theta, r_in, r_out))

    EA = sum(EA_c)
    EI = sum(EI_c)
    EI_theta_bend = sum(EI_theta_bend_c)
    EA_theta = sum(EA_theta_c)

    if layers:
        r0 = min(l['r_in'] for l in layers)
        rn = max(l['r_out'] for l in layers)
        R = (r0 + rn) / 2
        t_wall = rn - r0
        thick_ratio = t_wall / R if R > 0 else 0
        const = np.pi/4 - 2/np.pi

        if thick_ratio < 0.1:
            Kp_raw = EI_theta_bend / (R**3 * const) if EI_theta_bend > 0 else 0.0
            model_used = "thin-wall (bending only)"
        else:
            compliance = 0.0
            if EI_theta_bend > 0:
                compliance += const * R**3 / EI_theta_bend
            if EA_theta > 0:
                compliance += const * R / EA_theta
            Kp_raw = 1.0 / compliance if compliance > 0 else 0.0
            if thick_ratio < 0.5:
                model_used = "thick-wall (bending + hoop tension)"
            else:
                model_used = "very thick wall (approximate)"

        Kp = Kp_raw * correction_factor

        if EI_theta_bend > 0:
            Kp_c = [ei / EI_theta_bend * Kp for ei in EI_theta_bend_c]
        else:
            Kp_c = [0.0] * len(layers)
    else:
        Kp = 0.0
        Kp_c = []
        model_used = "N/A"
        thick_ratio = 0.0

    return EA, EI, Kp, EA_c, EI_c, Kp_c, model_used, thick_ratio

def compute_along_length(structure, L_total, correction_factor=1.0, n=300):
    xs = np.linspace(0, L_total, n)
    EA_arr = np.zeros(n); EI_arr = np.zeros(n); Kp_arr = np.zeros(n)
    for i, x in enumerate(xs):
        layers = compute_at_x(structure, x)
        EA, EI, Kp, _, _, _, _, _ = compute_stiffness(layers, correction_factor)
        EA_arr[i] = EA; EI_arr[i] = EI; Kp_arr[i] = Kp
    return xs, EA_arr, EI_arr, Kp_arr

# ==================== 会话状态 ====================
if 'structure' not in st.session_state:
    st.session_state.structure = create_default_structure()
else:
    st.session_state.structure = normalize_structure(st.session_state.structure)
if 'L_total' not in st.session_state:
    st.session_state.L_total = 350.0
if 'x_pos' not in st.session_state:
    st.session_state.x_pos = 0.0
if 'kp_correction' not in st.session_state:
    st.session_state.kp_correction = 1.0

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("导管结构定义")
    L_total = st.number_input("导管总长度 (mm)", min_value=1.0,
                              value=st.session_state.L_total, step=10.0)
    st.session_state.L_total = L_total

    st.markdown("**层顺序：列表第一个为最外层**")

    with st.expander("➕ 添加新层"):
        new_type = st.selectbox("层类型", list(LAYER_TYPES.keys()), key="new_type")
        insert_pos = st.number_input("插入位置（0=最外，末尾=最内）",
                                     min_value=0,
                                     max_value=len(st.session_state.structure),
                                     value=len(st.session_state.structure),
                                     step=1, key="insert_pos")
        if st.button("添加层", key="add_layer_btn"):
            if st.session_state.structure:
                r_out_ref = st.session_state.structure[0]['data'].iloc[0]['外半径(mm)']
                r_in_ref = st.session_state.structure[-1]['data'].iloc[0]['内半径(mm)']
            else:
                r_out_ref, r_in_ref = 0.6, 0.4
            new_layer = {
                'name': f'Layer {len(st.session_state.structure)+1}',
                'type': new_type,
                'data': make_default_layer(new_type, L_total, r_in_ref, r_out_ref)
            }
            st.session_state.structure.insert(int(insert_pos), new_layer)
            st.rerun()

    st.markdown("---")
    st.markdown("**编辑各层**")

    for i, layer in enumerate(st.session_state.structure):
        with st.expander(f"第{i+1}层：{layer['name']}（{layer['type']}）", expanded=False):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                layer['name'] = st.text_input("名称（图表中显示）", value=layer['name'],
                                              key=f"name_{i}")
            with col2:
                new_type = st.selectbox(
                    "类型", list(LAYER_TYPES.keys()),
                    index=list(LAYER_TYPES.keys()).index(layer['type']),
                    key=f"type_{i}"
                )
                if new_type != layer['type']:
                    old = layer['data'].iloc[0].to_dict() if len(layer['data']) > 0 else {}
                    r_in = old.get('内半径(mm)', 0.4)
                    r_out = old.get('外半径(mm)', 0.45)
                    start = old.get('起始位置(mm)', 0.0)
                    end = old.get('结束位置(mm)', L_total)
                    layer['type'] = new_type
                    layer['data'] = make_default_layer(new_type, end, r_in, r_out)
                    layer['data'].loc[0, '起始位置(mm)'] = start
                    st.rerun()
            with col3:
                if st.button("删除", key=f"del_{i}"):
                    st.session_state.structure.pop(i)
                    st.rerun()

            st.caption(LAYER_TYPES[layer['type']]['caption'])
            layer['data'] = st.data_editor(
                layer['data'],
                num_rows="dynamic",
                use_container_width=True,
                key=f"data_{i}"
            )

    st.markdown("---")
    st.markdown("**抗压扁刚度修正**")
    kp_correction = st.number_input(
        "Kp 修正系数（理论值 × 系数 = 报告值）",
        min_value=0.01, max_value=10.0,
        value=float(st.session_state.kp_correction),
        step=0.01, format="%.3f",
        key="kp_correction_input"
    )
    st.session_state.kp_correction = kp_correction
    st.caption("默认 1.000（不修正）。若做过实验或有限元标定，填入实测值/理论值。")

    st.markdown("---")
    if st.button("恢复示例数据"):
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.session_state.kp_correction = 1.0
        st.rerun()

# ==================== 半径校验结果 ====================
st.header("Catheter Multi-layer Stiffness Analysis")

# 使用流程说明（可折叠）
with st.expander("📖 使用流程说明（点击展开）", expanded=False):
    st.markdown("""
### 一、定义导管结构

1. 在左侧设置导管总长度。
2. 点击「➕ 添加新层」添加层，或直接编辑现有层。
3. **层顺序**：列表中第一个为最外层，最后一个为最内层。默认顺序为 Hot Melt → Braid → Coil → PTFE。
4. 每层可选择三种类型之一：
   - **普通材料**：填写内半径、外半径、弹性模量。
   - **编织层**：填写内外半径、扁丝宽度/厚度、股数、每束根数、PPI、丝材模量、原始基体体积分数。编织角自动计算。
   - **弹簧圈**：填写内外半径、丝径、螺距、丝材模量、原始基体体积分数。
5. 每层的表格可添加多行，实现**沿轴向分段**。每行代表一段，指定起始位置、结束位置及该段参数。

### 二、热熔渗入

- 编织层和弹簧圈的**渗入热熔模量**自动取自当前位置最外层普通材料层（通常是 Hot Melt）。
- 无需手动输入，界面会显示当前位置读取到的热熔模量。
- 若未找到热熔层，渗入基体模量按 0 计算，并给出警告。

### 三、检查校验结果

- **错误（红色）**：阻止计算，必须修正。包括起始位置为负、内外半径倒置、外半径不大于内半径等。
- **警告（黄色）**：不阻止计算，但需留意。包括分段超出总长、相邻层间隙或重叠超过 5 µm 等。

### 四、查看沿长度刚度分布

- 主区域上方显示三条曲线：轴向刚度 EA、弯曲刚度 EI、抗压扁刚度 Kp。
- 滑动滑块选择轴向位置 x，曲线上的灰色虚线会同步标记该位置。
- 当前位置的所有结果（指标、截面图、贡献百分比）都基于该位置存在的层计算。

### 五、查看当前截面分析

- **三个指标**：当前位置的 EA、EI、Kp 数值。
- **壁厚比提示**：根据壁厚/半径比自动分档，并说明使用的模型和精度。
  - 薄壁（< 0.1）：Timoshenko 薄环理论，偏差 < 5%。
  - 厚壁（0.1 ~ 0.5）：曲梁修正 + 环向拉伸，预计偏差 10~40%。
  - 极厚壁（≥ 0.5）：近似估计，偏差 40~60%，建议有限元或实验标定。
- **截面图**：编织层用斜线填充，弹簧圈用叉线填充，普通材料纯色。
- **贡献百分比条形图**：各层对 EA、EI、Kp 的相对贡献。
- **层参数表**：包含 E_z、E_θ、V_f、V_void、编织角等。

### 六、Kp 修正系数（关键）

**目的**：将解析模型的理论值校准到实际值。

**使用流程**：

1. **薄壁导管（λ < 0.1）**：修正系数保持 1.000，直接使用理论值（精度高）。
2. **厚壁或极厚壁导管（λ ≥ 0.1）**：
   - 第一步：先用理论值（修正系数 = 1.000）估算。
   - 第二步：做一次实验（平板压缩测 F-ΔD）或有限元仿真，得到实测 Kp。
   - 第三步：计算修正系数 = 实测 Kp / 理论 Kp。
   - 第四步：将修正系数填入左侧输入框（例如 1.35 或 0.75）。
   - 第五步：后续同类导管可直接沿用该系数，无需重复标定。

**注意**：修正系数是经验值，只适用于与标定工况相近的导管。若结构、材料、壁厚比变化较大，建议重新标定。

### 七、保存与导出

- 当前配置存在浏览器会话中，刷新页面会保留。
- 若需持久化，可截图或手动记录参数。
- 若需对比多个版本，可分别保存截图，或自行导出 CSV。
    """)

structure = st.session_state.structure
L_total = st.session_state.L_total
kp_correction = st.session_state.kp_correction

errors, warnings = validate_structure(structure, L_total)
if errors:
    with st.expander(f"❌ 发现 {len(errors)} 个错误（请修正后再使用）", expanded=True):
        for e in errors:
            st.error(e)
if warnings:
    with st.expander(f"⚠️ 发现 {len(warnings)} 个警告", expanded=False):
        for w in warnings:
            st.warning(w)

if errors:
    st.stop()

# ==================== 主区域 ====================
x_pos = st.slider("Axial position x (mm)", min_value=0.0, max_value=L_total,
                  value=st.session_state.x_pos, step=0.5)
st.session_state.x_pos = x_pos

xs, EA_arr, EI_arr, Kp_arr = compute_along_length(structure, L_total, kp_correction)

st.subheader("Stiffness along Length")
fig, axes = plt.subplots(3, 1, figsize=(10, 12))
fig.suptitle("Stiffness Distribution along Catheter Length", y=0.98, fontsize=14)

axes[0].plot(xs, EA_arr, 'b-', linewidth=2)
axes[0].set_ylabel('Axial Stiffness EA (N)')
axes[0].set_title('Axial Stiffness (uses E_z)')
axes[0].grid(True)
axes[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[1].plot(xs, EI_arr, 'g-', linewidth=2)
axes[1].set_ylabel('Bending Stiffness EI (N·mm²)')
axes[1].set_title('Bending Stiffness (uses E_z)')
axes[1].grid(True)
axes[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[2].plot(xs, Kp_arr, 'r-', linewidth=2)
axes[2].set_ylabel('Crush Stiffness Kp (N/mm)')
axes[2].set_xlabel('Axial position (mm)')
axes[2].set_title(f'Crush Stiffness (correction × {kp_correction:.3f})')
axes[2].grid(True)
axes[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

fig.tight_layout(rect=[0, 0, 1, 0.96])
st.pyplot(fig)

st.subheader(f"Cross-section Analysis at x = {x_pos:.1f} mm")
layers = compute_at_x(structure, x_pos)

if not layers:
    st.warning("该位置没有层存在。")
else:
    EA, EI, Kp, EA_c, EI_c, Kp_c, model_used, thick_ratio = compute_stiffness(layers, kp_correction)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Axial Stiffness EA", f"{EA:.2f} N")
    c2.metric("Total Bending Stiffness EI", f"{EI:.2f} N·mm²")
    c3.metric("Total Crush Stiffness Kp", f"{Kp:.2f} N/mm")

    # 三档壁厚提示
    if thick_ratio < 0.1:
        st.info(
            f"壁厚/半径比 = **{thick_ratio:.3f}** < 0.1（薄壁）。"
            f"抗压扁模型：**{model_used}**。Timoshenko 薄环理论，精度高（偏差 < 5%）。"
            f"当前修正系数：**{kp_correction:.3f}**。"
        )
    elif thick_ratio < 0.5:
        st.warning(
            f"壁厚/半径比 = **{thick_ratio:.3f}** ∈ [0.1, 0.5)（厚壁）。"
            f"抗压扁模型：**{model_used}**。"
            f"已包含曲梁弯曲修正和环向拉伸，未包含剪切。"
            f"预计偏差 10~40%，建议实验或有限元标定修正系数。"
            f"当前修正系数：**{kp_correction:.3f}**。"
        )
    else:
        st.error(
            f"壁厚/半径比 = **{thick_ratio:.3f}** ≥ 0.5（极厚壁）。"
            f"抗压扁模型：**{model_used}**。"
            f"当前解析模型为近似估计，预计偏差 40~60%。"
            f"强烈建议有限元或实验标定后填入修正系数。"
            f"当前修正系数：**{kp_correction:.3f}**。"
        )

    hot_melt_E = find_hot_melt_E(structure, x_pos)
    if hot_melt_E is not None:
        st.info(f"当前位置热熔层模量：{hot_melt_E:.1f} MPa（自动作为编织层和弹簧圈的渗入基体）")
    else:
        st.warning("未找到热熔层，渗入基体模量按 0 计算。")

    # 截面图
    st.subheader("Cross-section View")
    fig2, ax2 = plt.subplots(figsize=(5, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(layers), 1)))

    for i, l in enumerate(layers):
        r_in, r_out = l['r_in'], l['r_out']
        ax2.add_patch(plt.Circle((0, 0), r_out, color=colors[i], alpha=0.6))
        ax2.add_patch(plt.Circle((0, 0), r_in, color='white', fill=True))
        if l['type'] == '编织层':
            ax2.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360,
                                         width=r_out - r_in,
                                         fill=False, hatch='///', edgecolor='none'))
        elif l['type'] == '弹簧圈':
            ax2.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360,
                                         width=r_out - r_in,
                                         fill=False, hatch='xxx', edgecolor='none'))

    inner_r = min(l['r_in'] for l in layers)
    if inner_r > 0:
        ax2.add_patch(plt.Circle((0, 0), inner_r, color='white', fill=True))

    R_max = max(l['r_out'] for l in layers)
    ax2.set_xlim(-R_max*1.2, R_max*1.2)
    ax2.set_ylim(-R_max*1.2, R_max*1.2)
    ax2.set_aspect('equal')
    ax2.axis('off')
    st.pyplot(fig2)

    # 百分比条形图
    st.subheader("Layer Contributions (%)")
    labels = [l['name'] for l in layers]
    ea_pct = [v/EA*100 if EA > 0 else 0 for v in EA_c]
    ei_pct = [v/EI*100 if EI > 0 else 0 for v in EI_c]
    kp_pct = [v/Kp*100 if Kp > 0 else 0 for v in Kp_c]

    fig3, axes3 = plt.subplots(1, 3, figsize=(15, 4))
    fig3.suptitle("Layer Contributions to Stiffness (%)", y=1.02, fontsize=13)

    axes3[0].bar(labels, ea_pct, color=colors)
    axes3[0].set_title('Axial (EA) - uses E_z')
    axes3[0].set_ylabel('Contribution (%)')
    axes3[0].grid(axis='y', linestyle='--', alpha=0.6)

    axes3[1].bar(labels, ei_pct, color=colors)
    axes3[1].set_title('Bending (EI) - uses E_z')
    axes3[1].set_ylabel('Contribution (%)')
    axes3[1].grid(axis='y', linestyle='--', alpha=0.6)

    axes3[2].bar(labels, kp_pct, color=colors)
    axes3[2].set_title(f'Crush (Kp) - {model_used}')
    axes3[2].set_ylabel('Contribution (%)')
    axes3[2].grid(axis='y', linestyle='--', alpha=0.6)

    fig3.tight_layout(rect=[0, 0, 1, 0.95])
    st.pyplot(fig3)

    st.subheader("Contribution Summary")
    contrib_df = pd.DataFrame({
        "Layer": labels,
        "EA (%)": [f"{v:.2f}%" for v in ea_pct],
        "EI (%)": [f"{v:.2f}%" for v in ei_pct],
        "Kp (%)": [f"{v:.2f}%" for v in kp_pct]
    })
    st.dataframe(contrib_df, use_container_width=True)

    st.subheader("Layer Parameters at This Position")
    param_rows = []
    for l in layers:
        row = {
            "Layer": l['name'],
            "Type": l['type'],
            "r_in (mm)": l['r_in'],
            "r_out (mm)": l['r_out'],
            "E_z (MPa)": f"{l['E_z']:.2f}",
            "E_theta (MPa)": f"{l['E_theta']:.2f}",
        }
        row["V_f (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        row["V_void (%)"] = f"{l['V_void']*100:.2f}%" if l['V_void'] is not None else "—"
        row["Braid Angle (°)"] = f"{l['alpha']:.2f}" if l['alpha'] is not None else "—"
        param_rows.append(row)
    param_df = pd.DataFrame(param_rows)
    st.dataframe(param_df, use_container_width=True)
