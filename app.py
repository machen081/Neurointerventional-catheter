import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from copy import deepcopy

st.set_page_config(page_title="微导管截面多层刚度分析", layout="wide")

# ==================== 材料库 ====================
material_library = {
    "自定义": None,
    "PTFE": 500,
    "FEP": 400,
    "Pebax 3533": 10,
    "Pebax 5533": 30,
    "Pebax 7233": 50,
    "尼龙 12": 1500,
    "尼龙 6": 2500,
    "聚酰亚胺": 2500,
    "不锈钢 304": 200000,
    "镍钛合金": 60000,
    "钴铬合金": 220000,
}

# ==================== 计算函数（单点） ====================
def compute_layer_contributions(layers, x_pos):
    active_layers = []
    active_indices = []
    for idx, layer in enumerate(layers):
        if layer['start_x'] <= x_pos <= layer['end_x']:
            active_layers.append(layer)
            active_indices.append(idx)

    EA_contrib, EI_contrib, Kp_contrib = [], [], []
    for layer in active_layers:
        r_in, r_out, E_z = layer['r_in'], layer['r_out'], layer['E_z']
        EA_i = np.pi * E_z * (r_out**2 - r_in**2)
        EI_i = (np.pi / 4) * E_z * (r_out**4 - r_in**4)
        EA_contrib.append(EA_i)
        EI_contrib.append(EI_i)
        Kp_contrib.append(0.0)

    EA_total = sum(EA_contrib)
    EI_total = sum(EI_contrib)
    if active_layers:
        r0 = active_layers[0]['r_in']
        rn = active_layers[-1]['r_out']
        R = (r0 + rn) / 2
        Kp_total = EI_total / (R**3 * (np.pi/2 - 4/np.pi))
        if EI_total > 0:
            Kp_contrib = [ei / EI_total * Kp_total for ei in EI_contrib]
        else:
            Kp_contrib = [0.0] * len(active_layers)
    else:
        Kp_total = 0.0

    return EA_total, EI_total, Kp_total, EA_contrib, EI_contrib, Kp_contrib, active_layers, active_indices

# ==================== 新增：沿长度计算刚度曲线 ====================
def compute_stiffness_along_length(layers, L_total, n_points=500):
    x_vals = np.linspace(0, L_total, n_points)
    EA_arr = np.zeros(n_points)
    EI_arr = np.zeros(n_points)
    Kp_arr = np.zeros(n_points)
    for i, x in enumerate(x_vals):
        EA, EI, Kp, _, _, _, _, _ = compute_layer_contributions(layers, x)
        EA_arr[i] = EA
        EI_arr[i] = EI
        Kp_arr[i] = Kp
    return x_vals, EA_arr, EI_arr, Kp_arr

# ==================== 默认层数据 ====================
def create_default_layers():
    return [
        {"layer_type": "普通材料", "r_in": 0.40, "r_out": 0.45,
         "material": "PTFE", "E_z": 500, "start_x": 0.0, "end_x": 350.0},
        {"layer_type": "编织层", "r_in": 0.45, "r_out": 0.50,
         "d_w": 0.02, "alpha": 45.0, "PPI": 80,
         "E_f": 200000, "E_m": 30, "E_z": None,
         "start_x": 50.0, "end_x": 300.0},
        {"layer_type": "普通材料", "r_in": 0.50, "r_out": 0.60,
         "material": "Pebax 7233", "E_z": 50, "start_x": 0.0, "end_x": 350.0},
    ]

def update_braid_Ez(layer):
    d_w, alpha, PPI = layer['d_w'], layer['alpha'], layer['PPI']
    E_f, E_m = layer['E_f'], layer['E_m']
    r_in, r_out = layer['r_in'], layer['r_out']
    alpha_rad = np.radians(alpha)
    denom = 25.4 * 2 * (r_out**2 - r_in**2) * np.cos(alpha_rad)
    V_f = min(1.0, (np.pi * d_w**2 * PPI) / denom) if denom > 0 else 0.0
    Ez = E_f * V_f * (np.cos(alpha_rad)**4) + E_m * (1 - V_f)
    return Ez

# ==================== session_state 初始化 ====================
if 'layers' not in st.session_state:
    st.session_state.layers = create_default_layers()
if 'L_total' not in st.session_state:
    st.session_state.L_total = 350.0
if 'x_pos' not in st.session_state:
    st.session_state.x_pos = 0.0

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("截面层结构定义")

    L_total = st.number_input("导管总长度 (mm)", min_value=1.0,
                              value=st.session_state.L_total, step=10.0,
                              key="L_total_input")
    st.session_state.L_total = L_total

    n_layers = st.number_input("总层数", min_value=1, max_value=10,
                               value=len(st.session_state.layers), step=1,
                               key="n_layers_input")
    if n_layers != len(st.session_state.layers):
        if n_layers > len(st.session_state.layers):
            for _ in range(n_layers - len(st.session_state.layers)):
                last_layer = st.session_state.layers[-1]
                st.session_state.layers.append({
                    "layer_type": "普通材料",
                    "r_in": last_layer['r_out'],
                    "r_out": last_layer['r_out'] + 0.05,
                    "material": "自定义",
                    "E_z": 0.0,
                    "start_x": 0.0,
                    "end_x": L_total
                })
        else:
            st.session_state.layers = st.session_state.layers[:n_layers]
        st.rerun()

    layers_to_save = []
    valid = True
    for i, layer in enumerate(st.session_state.layers):
        with st.expander(f"第 {i+1} 层", expanded=(i == 0)):
            layer_type = st.radio("层类型", ["普通材料", "编织层"],
                                  horizontal=True,
                                  key=f"layer_{i}_type",
                                  index=0 if layer.get('layer_type') == '普通材料' else 1)
            layer['layer_type'] = layer_type

            col1, col2 = st.columns(2)
            with col1:
                r_in = st.number_input("内半径 (mm)", value=float(layer['r_in']),
                                       step=0.01, format="%.3f", key=f"layer_{i}_rin")
            with col2:
                r_out = st.number_input("外半径 (mm)", value=float(layer['r_out']),
                                        step=0.01, format="%.3f", key=f"layer_{i}_rout")
            if r_out <= r_in:
                st.error("外半径必须大于内半径")
                valid = False
            layer['r_in'], layer['r_out'] = r_in, r_out

            col3, col4 = st.columns(2)
            with col3:
                start_x = st.number_input("开始坐标 (mm)", value=float(layer.get('start_x', 0.0)),
                                          step=1.0, key=f"layer_{i}_start_x")
            with col4:
                end_x = st.number_input("结束坐标 (mm)", value=float(layer.get('end_x', L_total)),
                                        step=1.0, key=f"layer_{i}_end_x")
            if end_x <= start_x:
                st.error("结束坐标必须大于开始坐标")
                valid = False
            layer['start_x'] = start_x
            layer['end_x'] = end_x

            if layer_type == "普通材料":
                material = st.selectbox("材料", list(material_library.keys()),
                                        key=f"layer_{i}_material",
                                        index=list(material_library.keys()).index(layer.get('material', '自定义')))
                layer['material'] = material
                default_E = material_library[material] if material != "自定义" else 0.0

                Ez_key = f"layer_{i}_Ez"
                prev_material_key = f"layer_{i}_material_prev"
                if Ez_key not in st.session_state:
                    st.session_state[Ez_key] = float(layer.get('E_z', default_E))
                    st.session_state[prev_material_key] = material
                elif st.session_state.get(prev_material_key) != material:
                    st.session_state[Ez_key] = default_E
                    st.session_state[prev_material_key] = material

                E_z = st.number_input("轴向模量 (MPa)", key=Ez_key,
                                      step=100.0, format="%.1f")
                layer['E_z'] = E_z

            else:  # 编织层
                col1, col2 = st.columns(2)
                with col1:
                    d_w = st.number_input("编织丝直径 (mm)", value=float(layer.get('d_w', 0.02)),
                                          step=0.005, format="%.3f", key=f"layer_{i}_dw")
                    alpha = st.number_input("编织角 (度)", value=float(layer.get('alpha', 45.0)),
                                            step=1.0, key=f"layer_{i}_alpha")
                with col2:
                    PPI = st.number_input("PPI (1/in)", value=int(layer.get('PPI', 80)),
                                          step=5, key=f"layer_{i}_PPI")
                    E_f = st.number_input("丝材模量 (MPa)", value=float(layer.get('E_f', 200000)),
                                          step=1000.0, key=f"layer_{i}_Ef")
                E_m = st.number_input("基体模量 (MPa)", value=float(layer.get('E_m', 30)),
                                      step=1.0, key=f"layer_{i}_Em")

                layer.update({'d_w': d_w, 'alpha': alpha, 'PPI': PPI,
                              'E_f': E_f, 'E_m': E_m})
                Ez_calc = update_braid_Ez(layer)
                layer['E_z'] = Ez_calc
                st.success(f"编织层等效轴向模量 E_z = {Ez_calc:.1f} MPa")

            layers_to_save.append(layer)

    for i in range(1, len(layers_to_save)):
        if abs(layers_to_save[i]['r_in'] - layers_to_save[i-1]['r_out']) > 1e-6:
            st.warning(f"第 {i+1} 层内半径与上一层外半径不一致（可能在轴向上不同段可忽略）")

    if st.button("保存修改", type="primary"):
        if valid:
            st.session_state.layers = layers_to_save
            st.success("参数已保存")
            st.rerun()
        else:
            st.error("请修正错误后再保存")

    if st.button("恢复示例数据"):
        st.session_state.layers = create_default_layers()
        st.session_state.L_total = 350.0
        st.session_state.x_pos = 0.0
        st.rerun()

# ==================== 主区域 ====================
st.header("Cross-section Multi-layer Stiffness Analysis")

if not st.session_state.layers:
    st.info("请在左侧定义至少一层")
else:
    layers = st.session_state.layers
    L_total = st.session_state.L_total

    # 计算沿长度刚度曲线
    x_vals, EA_curve, EI_curve, Kp_curve = compute_stiffness_along_length(layers, L_total)

    # 绘制沿轴向的三个刚度曲线图
    st.subheader("Stiffness along Catheter Length")
    fig_curve, axes_curve = plt.subplots(3, 1, figsize=(10, 12))
    fig_curve.suptitle("Stiffness Distribution along Length", y=0.98, fontsize=14)

    axes_curve[0].plot(x_vals, EA_curve, 'b-', linewidth=2)
    axes_curve[0].set_ylabel('Axial Stiffness EA (N)', fontsize=10)
    axes_curve[0].grid(True)
    axes_curve[0].set_title('Axial Stiffness', fontsize=12)

    axes_curve[1].plot(x_vals, EI_curve, 'g-', linewidth=2)
    axes_curve[1].set_ylabel('Bending Stiffness EI (N·mm²)', fontsize=10)
    axes_curve[1].grid(True)
    axes_curve[1].set_title('Bending Stiffness', fontsize=12)

    axes_curve[2].plot(x_vals, Kp_curve, 'r-', linewidth=2)
    axes_curve[2].set_xlabel('Axial position (mm)', fontsize=10)
    axes_curve[2].set_ylabel('Crush Stiffness Kp (N/mm)', fontsize=10)
    axes_curve[2].grid(True)
    axes_curve[2].set_title('Crush Stiffness', fontsize=12)

    # 标记当前滑块位置
    for ax in axes_curve:
        ax.axvline(x=st.session_state.x_pos, color='gray', linestyle='--', alpha=0.5)

    fig_curve.tight_layout(rect=[0, 0, 1, 0.95])
    st.pyplot(fig_curve)

    # 轴向位置选择器
    st.subheader("Select Axial Position")
    x_pos = st.slider("Axial position x (mm)", min_value=0.0,
                      max_value=L_total, value=st.session_state.x_pos,
                      step=0.5, key="x_pos_slider")
    st.session_state.x_pos = x_pos

    try:
        EA_total, EI_total, Kp_total, EA_contrib, EI_contrib, Kp_contrib, active_layers, active_indices = compute_layer_contributions(layers, x_pos)
    except Exception as e:
        st.error(f"计算错误: {e}")
        st.stop()

    if not active_layers:
        st.warning(f"在 x = {x_pos:.1f} mm 处没有层存在。")
        st.stop()

    # 指标
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Axial Stiffness EA", f"{EA_total:.2f} N")
    c2.metric("Total Bending Stiffness EI", f"{EI_total:.2f} N·mm²")
    c3.metric("Total Crush Stiffness Kp", f"{Kp_total:.2f} N/mm")

    # 截面图
    st.subheader("Cross-section View")
    fig, ax = plt.subplots(figsize=(5, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, len(active_layers)))

    for i in reversed(range(len(active_layers))):
        layer = active_layers[i]
        r_in, r_out = layer['r_in'], layer['r_out']
        ax.add_patch(plt.Circle((0, 0), r_out, color=colors[i], alpha=0.6))
        ax.add_patch(plt.Circle((0, 0), r_in, color='white', fill=True))
        if layer.get('layer_type') == '编织层':
            ax.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360,
                                        width=r_out - r_in,
                                        fill=False, hatch='///', edgecolor='none'))

    if active_layers[0]['r_in'] > 0:
        ax.add_patch(plt.Circle((0, 0), active_layers[0]['r_in'], color='white', fill=True))

    for i, layer in enumerate(active_layers):
        r_mid = (layer['r_in'] + layer['r_out']) / 2
        global_idx = active_indices[i]
        ax.text(0, r_mid, f"L{global_idx+1}", ha='center', va='center', fontsize=9,
                bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))

    ax.set_xlim(-active_layers[-1]['r_out']*1.2, active_layers[-1]['r_out']*1.2)
    ax.set_ylim(-active_layers[-1]['r_out']*1.2, active_layers[-1]['r_out']*1.2)
    ax.set_aspect('equal')
    ax.axis('off')
    st.pyplot(fig)

    # 百分比计算
    ea_pct = [v/EA_total*100 if EA_total > 0 else 0 for v in EA_contrib]
    ei_pct = [v/EI_total*100 if EI_total > 0 else 0 for v in EI_contrib]
    kp_pct = [v/Kp_total*100 if Kp_total > 0 else 0 for v in Kp_contrib]

    # 条形图
    st.subheader("Layer Contributions (%) - Bar Chart")
    labels = [f"L{active_indices[i]+1}" for i in range(len(active_layers))]
    fig_bar, axes_bar = plt.subplots(1, 3, figsize=(15, 5))
    fig_bar.suptitle("Layer Contributions to Stiffness (%)", y=1.02, fontsize=14)

    axes_bar[0].bar(labels, ea_pct, color=colors)
    axes_bar[0].set_title('Axial Stiffness (EA) %')
    axes_bar[0].set_ylabel('Contribution (%)')
    axes_bar[0].grid(axis='y', linestyle='--', alpha=0.7)

    axes_bar[1].bar(labels, ei_pct, color=colors)
    axes_bar[1].set_title('Bending Stiffness (EI) %')
    axes_bar[1].set_ylabel('Contribution (%)')
    axes_bar[1].grid(axis='y', linestyle='--', alpha=0.7)

    axes_bar[2].bar(labels, kp_pct, color=colors)
    axes_bar[2].set_title('Crush Stiffness (Kp) %')
    axes_bar[2].set_ylabel('Contribution (%)')
    axes_bar[2].grid(axis='y', linestyle='--', alpha=0.7)

    fig_bar.tight_layout(rect=[0, 0, 1, 0.95])
    st.pyplot(fig_bar)

    # 百分比表格
    st.subheader("Layer Contributions (%)")
    contrib_df = pd.DataFrame({
        "Layer": labels,
        "EA (%)": [f"{v:.2f}%" for v in ea_pct],
        "EI (%)": [f"{v:.2f}%" for v in ei_pct],
        "Kp (%)": [f"{v:.2f}%" for v in kp_pct]
    })
    st.dataframe(contrib_df, use_container_width=True)

    # 层参数表（显示所有层，包括轴向范围）
    st.subheader("Layer Parameters")
    all_keys = ['layer_type', 'r_in', 'r_out', 'material', 'E_z',
                'd_w', 'alpha', 'PPI', 'E_f', 'E_m', 'start_x', 'end_x']
    df_rows = []
    for idx, layer in enumerate(layers):
        row = {"Layer": f"L{idx+1}"}
        for k in all_keys:
            row[k] = layer.get(k, None)
        df_rows.append(row)
    df = pd.DataFrame(df_rows)
    df = df.fillna('—')
    st.dataframe(df, use_container_width=True)
