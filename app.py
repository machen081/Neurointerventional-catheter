import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(page_title="微导管多层结构刚度分析", layout="wide")

# ==================== 层类型定义 ====================
LAYER_TYPES = {
    '普通材料': {
        'columns': ['start_x', 'end_x', 'r_in', 'r_out', 'E'],
        'default': {'start_x': 0.0, 'end_x': 350.0, 'r_in': 0.40, 'r_out': 0.45, 'E': 500.0},
        'caption': '列：start_x, end_x, r_in, r_out, E（轴向模量 MPa）'
    },
    '编织层': {
        'columns': ['start_x', 'end_x', 'r_in', 'r_out', 'w', 't',
                    'N_strands', 'n_per_bundle', 'alpha', 'PPI', 'E_f', 'E_m'],
        'default': {'start_x': 0.0, 'end_x': 350.0, 'r_in': 0.45, 'r_out': 0.55,
                    'w': 0.05, 't': 0.02, 'N_strands': 16, 'n_per_bundle': 1,
                    'alpha': 45.0, 'PPI': 80, 'E_f': 200000.0, 'E_m': 50.0},
        'caption': '列：start_x, end_x, r_in, r_out, w（扁丝宽 mm）, t（扁丝厚 mm）, '
                   'N_strands（股数）, n_per_bundle（每束根数）, alpha（编织角°）, '
                   'PPI, E_f（丝材模量 MPa）, E_m（渗入热熔模量 MPa）'
    },
    '弹簧圈': {
        'columns': ['start_x', 'end_x', 'r_in', 'r_out', 'd_w', 'pitch', 'E_f', 'E_m'],
        'default': {'start_x': 0.0, 'end_x': 350.0, 'r_in': 0.42, 'r_out': 0.45,
                    'd_w': 0.02, 'pitch': 0.10, 'E_f': 200000.0, 'E_m': 50.0},
        'caption': '列：start_x, end_x, r_in, r_out, d_w（丝径 mm）, pitch（螺距 mm）, '
                   'E_f（丝材模量 MPa）, E_m（渗入热熔模量 MPa）'
    },
}

def make_default_layer(layer_type, L_total=350, r_in=0.4, r_out=0.45):
    d = LAYER_TYPES[layer_type]['default'].copy()
    d['end_x'] = L_total
    d['r_in'] = r_in
    d['r_out'] = r_out
    return pd.DataFrame([d])

def create_default_structure(L_total=350):
    """从外到内：热熔层 → 编织层 → 弹簧圈 → PTFE"""
    return [
        {'name': 'Hot Melt', 'type': '普通材料',
         'data': pd.DataFrame([{'start_x': 0.0, 'end_x': L_total,
                                'r_in': 0.55, 'r_out': 0.60, 'E': 50.0}])},
        {'name': 'Braid', 'type': '编织层',
         'data': pd.DataFrame([{'start_x': 0.0, 'end_x': L_total,
                                'r_in': 0.45, 'r_out': 0.55,
                                'w': 0.05, 't': 0.02, 'N_strands': 16,
                                'n_per_bundle': 1, 'alpha': 45.0, 'PPI': 80,
                                'E_f': 200000.0, 'E_m': 50.0}])},
        {'name': 'Coil', 'type': '弹簧圈',
         'data': pd.DataFrame([{'start_x': 0.0, 'end_x': L_total,
                                'r_in': 0.42, 'r_out': 0.45,
                                'd_w': 0.02, 'pitch': 0.10,
                                'E_f': 200000.0, 'E_m': 50.0}])},
        {'name': 'PTFE', 'type': '普通材料',
         'data': pd.DataFrame([{'start_x': 0.0, 'end_x': L_total,
                                'r_in': 0.40, 'r_out': 0.42, 'E': 500.0}])},
    ]

# ==================== 分段查找 ====================
def find_segment(df, x):
    if df is None or df.empty:
        return None
    for _, row in df.iterrows():
        try:
            if row['start_x'] <= x <= row['end_x']:
                return row
        except Exception:
            continue
    return None

# ==================== 等效模量计算 ====================
def compute_braid_E(row):
    """编织层（扁丝）等效轴向模量，返回 (E_z, V_f)"""
    w = row['w']; t = row['t']
    N = row['N_strands']; n_s = row['n_per_bundle']
    alpha = row['alpha']; E_f = row['E_f']; E_m = row['E_m']
    r_in, r_out = row['r_in'], row['r_out']

    alpha_rad = np.radians(alpha)
    denom = np.pi * (r_out**2 - r_in**2) * np.cos(alpha_rad)
    if denom > 0:
        V_f = min(1.0, 2 * N * n_s * w * t / denom)
    else:
        V_f = 0.0
    E_z = E_f * V_f * (np.cos(alpha_rad)**4) + E_m * (1 - V_f)
    return E_z, V_f

def compute_coil_E(row):
    """弹簧圈等效轴向模量（螺旋弹簧 + 热熔基体并联）"""
    d = row['d_w']; pitch = row['pitch']
    E_f = row['E_f']; E_m = row['E_m']
    r_in, r_out = row['r_in'], row['r_out']
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
    """返回位置 x 处的层列表（从外到内）"""
    layers = []
    for idx, layer in enumerate(structure):
        row = find_segment(layer['data'], x)
        if row is None:
            continue
        ltype = layer['type']
        if ltype == '普通材料':
            E_z = row['E']; V_f = None
        elif ltype == '编织层':
            E_z, V_f = compute_braid_E(row)
        elif ltype == '弹簧圈':
            E_z = compute_coil_E(row); V_f = None
        else:
            continue
        layers.append({
            'name': layer['name'],
            'type': ltype,
            'r_in': row['r_in'],
            'r_out': row['r_out'],
            'E_z': E_z,
            'V_f': V_f,
            'layer_idx': idx
        })
    # 从外到内排序
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
    st.markdown("热熔层通过各层的 **E_m** 参数体现渗入效应。")

    # ---------- 添加新层 ----------
    with st.expander("➕ 添加新层"):
        new_type = st.selectbox("层类型", list(LAYER_TYPES.keys()), key="new_type")
        insert_pos = st.number_input("插入位置（0=最外，末尾=最内）",
                                     min_value=0,
                                     max_value=len(st.session_state.structure),
                                     value=len(st.session_state.structure),
                                     step=1, key="insert_pos")
        if st.button("添加层", key="add_layer_btn"):
            # 参考现有层的半径
            if st.session_state.structure:
                r_out_ref = st.session_state.structure[0]['data'].iloc[0]['r_out']
                r_in_ref = st.session_state.structure[-1]['data'].iloc[0]['r_in']
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

    # ---------- 逐层编辑 ----------
    for i, layer in enumerate(st.session_state.structure):
        with st.expander(f"L{i+1}: {layer['name']} ({layer['type']})", expanded=False):
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
                    # 类型改变，用默认值重建数据，保留半径
                    old = layer['data'].iloc[0] if len(layer['data']) > 0 else {}
                    r_in = old.get('r_in', 0.4)
                    r_out = old.get('r_out', 0.45)
                    layer['type'] = new_type
                    layer['data'] = make_default_layer(new_type, L_total, r_in, r_out)
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
            "Layer": l['name'],
            "Type": l['type'],
            "r_in (mm)": l['r_in'],
            "r_out (mm)": l['r_out'],
            "E_z (MPa)": f"{l['E_z']:.2f}"
        }
        row["V_f (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        param_rows.append(row)
    param_df = pd.DataFrame(param_rows)
    st.dataframe(param_df, use_container_width=True)
