import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(page_title="微导管多层结构刚度分析", layout="wide")

# ==================== 层类型定义（中文列名） ====================
LAYER_TYPES = {
    '普通材料': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)', '弹性模量(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 350.0,
                    '内半径(mm)': 0.40, '外半径(mm)': 0.45, '弹性模量(MPa)': 500.0},
        'caption': '普通材料：弹性模量由材料决定'
    },
    '编织层': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '扁丝宽度(mm)', '扁丝厚度(mm)', '股数', '每束根数',
                    '编织角(°)', '每英寸交叉数', '丝材模量(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 350.0,
                    '内半径(mm)': 0.45, '外半径(mm)': 0.55,
                    '扁丝宽度(mm)': 0.05, '扁丝厚度(mm)': 0.02,
                    '股数': 16, '每束根数': 1, '编织角(°)': 45.0,
                    '每英寸交叉数': 80, '丝材模量(MPa)': 200000.0},
        'caption': '编织层（扁丝）：渗入热熔模量自动取自最外层热熔层'
    },
    '弹簧圈': {
        'columns': ['起始位置(mm)', '结束位置(mm)', '内半径(mm)', '外半径(mm)',
                    '丝径(mm)', '螺距(mm)', '丝材模量(MPa)'],
        'default': {'起始位置(mm)': 0.0, '结束位置(mm)': 350.0,
                    '内半径(mm)': 0.42, '外半径(mm)': 0.45,
                    '丝径(mm)': 0.02, '螺距(mm)': 0.10, '丝材模量(MPa)': 200000.0},
        'caption': '弹簧圈：渗入热熔模量自动取自最外层热熔层'
    },
}

def make_default_layer(layer_type, L_total=350, r_in=0.4, r_out=0.45):
    d = LAYER_TYPES[layer_type]['default'].copy()
    d['结束位置(mm)'] = L_total
    d['内半径(mm)'] = r_in
    d['外半径(mm)'] = r_out
    return pd.DataFrame([d])

def create_default_structure(L_total=350):
    """从外到内：热熔层 → 编织层 → 弹簧圈 → PTFE"""
    return [
        {'name': '热熔层', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.55, '外半径(mm)': 0.60,
                                '弹性模量(MPa)': 50.0}])},
        {'name': '编织层', 'type': '编织层',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.45, '外半径(mm)': 0.55,
                                '扁丝宽度(mm)': 0.05, '扁丝厚度(mm)': 0.02,
                                '股数': 16, '每束根数': 1, '编织角(°)': 45.0,
                                '每英寸交叉数': 80, '丝材模量(MPa)': 200000.0}])},
        {'name': '弹簧圈', 'type': '弹簧圈',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.42, '外半径(mm)': 0.45,
                                '丝径(mm)': 0.02, '螺距(mm)': 0.10,
                                '丝材模量(MPa)': 200000.0}])},
        {'name': 'PTFE', 'type': '普通材料',
         'data': pd.DataFrame([{'起始位置(mm)': 0.0, '结束位置(mm)': L_total,
                                '内半径(mm)': 0.40, '外半径(mm)': 0.42,
                                '弹性模量(MPa)': 500.0}])},
    ]

# ==================== 数据规范化（兼容旧格式） ====================
def normalize_structure(structure):
    for layer in structure:
        expected_cols = LAYER_TYPES[layer['type']]['columns']
        df = layer['data']
        if list(df.columns) != expected_cols:
            # 列名不匹配，重建该层数据
            old = df.iloc[0].to_dict() if len(df) > 0 else {}
            r_in = old.get('内半径(mm)', old.get('r_in', 0.4))
            r_out = old.get('外半径(mm)', old.get('r_out', 0.45))
            start = old.get('起始位置(mm)', old.get('start_x', 0.0))
            end = old.get('结束位置(mm)', old.get('end_x', 350.0))
            new_df = make_default_layer(layer['type'], end, r_in, r_out)
            new_df.loc[0, '起始位置(mm)'] = start
            layer['data'] = new_df
    return structure

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

# ==================== 查找热熔层模量（防呆设计） ====================
def find_hot_melt_E(structure, x):
    """
    在位置 x 处查找最外层的热熔层（普通材料层），返回其弹性模量。
    若未找到，返回 None。
    """
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
    # 取外半径最大的普通材料层作为热熔层
    candidates.sort(key=lambda c: -c[0])
    return candidates[0][1]

# ==================== 等效模量计算 ====================
def compute_braid_E(row, E_m):
    """编织层（扁丝）等效轴向模量，返回 (E_z, V_f)。E_m 为渗入热熔模量"""
    if E_m is None:
        E_m = 0.0
    w = row['扁丝宽度(mm)']; t = row['扁丝厚度(mm)']
    N = row['股数']; n_s = row['每束根数']
    alpha = row['编织角(°)']; E_f = row['丝材模量(MPa)']
    r_in, r_out = row['内半径(mm)'], row['外半径(mm)']

    alpha_rad = np.radians(alpha)
    denom = np.pi * (r_out**2 - r_in**2) * np.cos(alpha_rad)
    if denom > 0:
        V_f = min(1.0, 2 * N * n_s * w * t / denom)
    else:
        V_f = 0.0
    E_z = E_f * V_f * (np.cos(alpha_rad)**4) + E_m * (1 - V_f)
    return E_z, V_f

def compute_coil_E(row, E_m):
    """弹簧圈等效轴向模量（螺旋弹簧 + 热熔基体并联）。E_m 为渗入热熔模量"""
    if E_m is None:
        E_m = 0.0
    d = row['丝径(mm)']; pitch = row['螺距(mm)']
    E_f = row['丝材模量(MPa)']
    r_in, r_out = row['内半径(mm)'], row['外半径(mm)']
    nu = 0.3
    G = E_f / (2 * (1 + nu))
    D = r_in + r_out
    A = np.pi * (r_out**2 - r_in**2)
    if pitch > 0 and r_out > r_in:
        V_spring = min(1.0, (np.pi * d**2 / 4) / (pitch * (r_out - r_in)))
    else:
        V_spring = 0.0
    if D > 0 and A > 0 and pitch > 0:
        E_spring = G * d**4 * pitch / (8 * D**3 * A)
    else:
        E_spring = 0.0
    return E_spring + E_m * (1 - V_spring)

# ==================== 截面生成 ====================
def compute_at_x(structure, x):
    """返回位置 x 处的层列表（从外到内），自动读取热熔层模量作为基体"""
    hot_melt_E = find_hot_melt_E(structure, x)
    layers = []
    for idx, layer in enumerate(structure):
        row = find_segment(layer['data'], x)
        if row is None:
            continue
        ltype = layer['type']
        try:
            if ltype == '普通材料':
                E_z = row['弹性模量(MPa)']
                V_f = None
            elif ltype == '编织层':
                E_z, V_f = compute_braid_E(row, hot_melt_E)
            elif ltype == '弹簧圈':
                E_z = compute_coil_E(row, hot_melt_E)
                V_f = None
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
            'V_f': V_f,
            'layer_idx': idx
        })
    layers.sort(key=lambda l: -l['r_out'])
    return layers

# ==================== 刚度计算 ====================
def compute_stiffness(layers):
    EA_c, EI_c = [], []
    for l in layers:
        r_in, r_out, E_z = l['r_in'], l['r_out'], l['E_z']
        EA_c.append(np.pi * E_z * (r_out**2 - r_in**2))
        EI_c.append((np.pi / 4) * E_z * (r_out**4 - r_in**4))
    EA = sum(EA_c)
    EI = sum(EI_c)
    if layers:
        r0 = min(l['r_in'] for l in layers)
        rn = max(l['r_out'] for l in layers)
        R = (r0 + rn) / 2
        Kp = EI / (R**3 * (np.pi/2 - 4/np.pi))
        Kp_c = [ei / EI * Kp for ei in EI_c] if EI > 0 else [0.0]*len(layers)
    else:
        Kp = 0.0
        Kp_c = []
    return EA, EI, Kp, EA_c, EI_c, Kp_c

def compute_along_length(structure, L_total, n=300):
    xs = np.linspace(0, L_total, n)
    EA_arr = np.zeros(n); EI_arr = np.zeros(n); Kp_arr = np.zeros(n)
    for i, x in enumerate(xs):
        layers = compute_at_x(structure, x)
        EA, EI, Kp, _, _, _ = compute_stiffness(layers)
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

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("导管结构定义")
    L_total = st.number_input("导管总长度 (mm)", min_value=1.0,
                              value=st.session_state.L_total, step=10.0)
    st.session_state.L_total = L_total

    st.markdown("**层顺序：列表第一个为最外层**")
    st.info("渗入热熔模量由程序自动从当前位置最外层热熔层读取，无需手动输入。")

    # ---------- 添加新层 ----------
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
                'name': f'第{len(st.session_state.structure)+1}层',
                'type': new_type,
                'data': make_default_layer(new_type, L_total, r_in_ref, r_out_ref)
            }
            st.session_state.structure.insert(int(insert_pos), new_layer)
            st.rerun()

    st.markdown("---")
    st.markdown("**编辑各层**")

    # ---------- 逐层编辑 ----------
    for i, layer in enumerate(st.session_state.structure):
        with st.expander(f"第{i+1}层：{layer['name']}（{layer['type']}）", expanded=False):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                layer['name'] = st.text_input("名称", value=layer['name'],
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
    if st.button("恢复示例数据"):
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层结构刚度分析")

structure = st.session_state.structure
L_total = st.session_state.L_total

x_pos = st.slider("轴向位置 x (mm)", min_value=0.0, max_value=L_total,
                  value=st.session_state.x_pos, step=0.5)
st.session_state.x_pos = x_pos

# 沿长度刚度曲线
xs, EA_arr, EI_arr, Kp_arr = compute_along_length(structure, L_total)

st.subheader("Stiffness along Length")
fig, axes = plt.subplots(3, 1, figsize=(10, 12))
fig.suptitle("Stiffness Distribution along Catheter Length", y=0.98, fontsize=14)

axes[0].plot(xs, EA_arr, 'b-', linewidth=2)
axes[0].set_ylabel('Axial Stiffness EA (N)')
axes[0].set_title('Axial Stiffness')
axes[0].grid(True)
axes[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[1].plot(xs, EI_arr, 'g-', linewidth=2)
axes[1].set_ylabel('Bending Stiffness EI (N·mm²)')
axes[1].set_title('Bending Stiffness')
axes[1].grid(True)
axes[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

axes[2].plot(xs, Kp_arr, 'r-', linewidth=2)
axes[2].set_ylabel('Crush Stiffness Kp (N/mm)')
axes[2].set_xlabel('Axial position (mm)')
axes[2].set_title('Crush Stiffness')
axes[2].grid(True)
axes[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)

fig.tight_layout(rect=[0, 0, 1, 0.96])
st.pyplot(fig)

# 当前截面分析
st.subheader(f"Cross-section Analysis at x = {x_pos:.1f} mm")
layers = compute_at_x(structure, x_pos)

if not layers:
    st.warning("该位置没有层存在。")
else:
    EA, EI, Kp, EA_c, EI_c, Kp_c = compute_stiffness(layers)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Axial Stiffness EA", f"{EA:.2f} N")
    c2.metric("Total Bending Stiffness EI", f"{EI:.2f} N·mm²")
    c3.metric("Total Crush Stiffness Kp", f"{Kp:.2f} N/mm")

    # 显示当前热熔层模量（防呆提示）
    hot_melt_E = find_hot_melt_E(structure, x_pos)
    if hot_melt_E is not None:
        st.info(f"当前位置热熔层模量：{hot_melt_E:.1f} MPa（已作为编织层和弹簧圈的渗入基体模量）")
    else:
        st.warning("当前位置未找到热熔层（普通材料层），编织层和弹簧圈的渗入基体模量按 0 计算。")

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

    for i, l in enumerate(layers):
        r_mid = (l['r_in'] + l['r_out']) / 2
        ax2.text(0, r_mid, l['name'], ha='center', va='center', fontsize=8,
                 bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

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
    axes3[0].set_title('Axial Stiffness (EA) %')
    axes3[0].set_ylabel('Contribution (%)')
    axes3[0].grid(axis='y', linestyle='--', alpha=0.6)

    axes3[1].bar(labels, ei_pct, color=colors)
    axes3[1].set_title('Bending Stiffness (EI) %')
    axes3[1].set_ylabel('Contribution (%)')
    axes3[1].grid(axis='y', linestyle='--', alpha=0.6)

    axes3[2].bar(labels, kp_pct, color=colors)
    axes3[2].set_title('Crush Stiffness (Kp) %')
    axes3[2].set_ylabel('Contribution (%)')
    axes3[2].grid(axis='y', linestyle='--', alpha=0.6)

    fig3.tight_layout(rect=[0, 0, 1, 0.95])
    st.pyplot(fig3)

    # 百分比表格
    st.subheader("Contribution Summary")
    contrib_df = pd.DataFrame({
        "Layer": labels,
        "EA (%)": [f"{v:.2f}%" for v in ea_pct],
        "EI (%)": [f"{v:.2f}%" for v in ei_pct],
        "Kp (%)": [f"{v:.2f}%" for v in kp_pct]
    })
    st.dataframe(contrib_df, use_container_width=True)

    # 层参数表
    st.subheader("Layer Parameters at This Position")
    param_rows = []
    for l in layers:
        row = {
            "层名称": l['name'],
            "类型": l['type'],
            "内半径 (mm)": l['r_in'],
            "外半径 (mm)": l['r_out'],
            "等效轴向模量 (MPa)": f"{l['E_z']:.2f}"
        }
        row["丝材体积分数 (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        param_rows.append(row)
    param_df = pd.DataFrame(param_rows)
    st.dataframe(param_df, use_container_width=True)
