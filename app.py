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

# ==================== 计算函数 ====================
def compute_layer_contributions(layers):
    EA_contrib, EI_contrib, Kp_contrib = [], [], []
    for layer in layers:
        r_in, r_out, E_z = layer['r_in'], layer['r_out'], layer['E_z']
        EA_i = np.pi * E_z * (r_out**2 - r_in**2)
        EI_i = (np.pi / 4) * E_z * (r_out**4 - r_in**4)
        EA_contrib.append(EA_i)
        EI_contrib.append(EI_i)
        Kp_contrib.append(0.0)

    EA_total = sum(EA_contrib)
    EI_total = sum(EI_contrib)
    if layers:
        r0 = layers[0]['r_in']
        rn = layers[-1]['r_out']
        R = (r0 + rn) / 2
        Kp_total = EI_total / (R**3 * (np.pi/2 - 4/np.pi))
        if EI_total > 0:
            Kp_contrib = [ei / EI_total * Kp_total for ei in EI_contrib]
        else:
            Kp_contrib = [0.0] * len(layers)
    else:
        Kp_total = 0.0
    return EA_total, EI_total, Kp_total, EA_contrib, EI_contrib, Kp_contrib

# ==================== 默认层数据 ====================
def create_default_layers():
    return [
        {"layer_type": "普通材料", "r_in": 0.40, "r_out": 0.45,
         "material": "PTFE", "E_z": 500},
        {"layer_type": "编织层", "r_in": 0.45, "r_out": 0.50,
         "d_w": 0.02, "alpha": 45.0, "PPI": 80,
         "E_f": 200000, "E_m": 30, "E_z": None},
        {"layer_type": "普通材料", "r_in": 0.50, "r_out": 0.60,
         "material": "Pebax 7233", "E_z": 50},
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

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("截面层结构定义")

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
                    "E_z": 0.0
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

    # 检查层间连续性
    for i in range(1, len(layers_to_save)):
        if abs(layers_to_save[i]['r_in'] - layers_to_save[i-1]['r_out']) > 1e-6:
            st.warning(f"第 {i+1} 层内半径与上一层外半径不一致")

    if st.button("保存修改", type="primary"):
        if valid:
            st.session_state.layers = layers_to_save
            st.success("参数已保存")
            st.rerun()
        else:
            st.error("请修正错误后再保存")

    if st.button("恢复示例数据"):
        st.session_state.layers = create_default_layers()
        st.rerun()

# ==================== 主区域 ====================
st.header("Cross-section Multi-layer Stiffness Analysis")

if not st.session_state.layers:
    st.info("请在左侧定义至少一层")
else:
    layers = st.session_state.layers
    try:
        EA_total, EI_total, Kp_total, EA_contrib, EI_contrib, Kp_contrib = compute_layer_contributions(layers)
    except Exception as e:
        st.error(f"计算错误: {e}")
        st.stop()

    # 指标
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Axial Stiffness EA", f"{EA_total:.2f} N")
    c2.metric("Total Bending Stiffness EI", f"{EI_total:.2f} N·mm²")
    c3.metric("Total Crush Stiffness Kp", f"{Kp_total:.2f} N/mm")

    # 截面图
    st.subheader("Cross-section View")
    fig, ax = plt.subplots(figsize=(5, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, len(layers)))

    # 从外向内绘制
    for idx in reversed(range(len(layers))):
        layer = layers[idx]
        r_in, r_out = layer['r_in'], layer['r_out']
        ax.add_patch(plt.Circle((0, 0), r_out, color=colors[idx], alpha=0.6))
        ax.add_patch(plt.Circle((0, 0), r_in, color='white', fill=True))
        if layer.get('layer_type') == '编织层':
            ax.add_patch(mpatches.Wedge((0, 0), r_out, 0, 360,
                                        width=r_out - r_in,
                                        fill=False, hatch='///', edgecolor='none'))

    if layers[0]['r_in'] > 0:
        ax.add_patch(plt.Circle((0, 0), layers[0]['r_in'], color='white', fill=True))

    # 标注层号
    for i, layer in enumerate(layers):
        r_mid = (layer['r_in'] + layer['r_out']) / 2
        ax.text(0, r_mid, f"L{i+1}", ha='center', va='center', fontsize=9,
                bbox=dict(facecolor='white', alpha=0.5, edgecolor='none'))

    ax.set_xlim(-layers[-1]['r_out']*1.2, layers[-1]['r_out']*1.2)
    ax.set_ylim(-layers[-1]['r_out']*1.2, layers[-1]['r_out']*1.2)
    ax.set_aspect('equal')
    ax.axis('off')
    st.pyplot(fig)

    # 百分比计算
    ea_pct = [v/EA_total*100 if EA_total > 0 else 0 for v in EA_contrib]
    ei_pct = [v/EI_total*100 if EI_total > 0 else 0 for v in EI_contrib]
    kp_pct = [v/Kp_total*100 if Kp_total > 0 else 0 for v in Kp_contrib]

    # 条形图
    st.subheader("Layer Contributions (%) - Bar Chart")
    labels = [f"L{i+1}" for i in range(len(layers))]
    fig_bar, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig_bar.suptitle("Layer Contributions to Stiffness (%)", y=1.02, fontsize=14)

    axes[0].bar(labels, ea_pct, color=colors)
    axes[0].set_title('Axial Stiffness (EA) %')
    axes[0].set_ylabel('Contribution (%)')
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)

    axes[1].bar(labels, ei_pct, color=colors)
    axes[1].set_title('Bending Stiffness (EI) %')
    axes[1].set_ylabel('Contribution (%)')
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)

    axes[2].bar(labels, kp_pct, color=colors)
    axes[2].set_title('Crush Stiffness (Kp) %')
    axes[2].set_ylabel('Contribution (%)')
    axes[2].grid(axis='y', linestyle='--', alpha=0.7)

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

    # 层参数表（补齐所有键，普通层编织参数显示为 —）
    st.subheader("Layer Parameters")
    all_keys = ['layer_type', 'r_in', 'r_out', 'material', 'E_z',
                'd_w', 'alpha', 'PPI', 'E_f', 'E_m']
    df_rows = []
    for layer in layers:
        row = {}
        for k in all_keys:
            row[k] = layer.get(k, None)
        df_rows.append(row)
    df = pd.DataFrame(df_rows)
    df = df.fillna('—')
    st.dataframe(df, use_container_width=True)
