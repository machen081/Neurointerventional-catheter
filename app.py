import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

st.set_page_config(page_title="微导管多层刚度计算器", layout="wide")

# ==================== 计算函数 ====================
def compute_stiffnesses(layers):
    """
    layers: list of dict, each dict has keys 'r_in', 'r_out', 'E_z'
    返回 EA (N), EI (N·mm²), Kp (N/mm)
    """
    EA = 0.0
    EI = 0.0
    for layer in layers:
        r_in = layer['r_in']
        r_out = layer['r_out']
        E_z = layer['E_z']
        if r_out <= r_in:
            raise ValueError(f"层内外半径错误：内半径 {r_in} 不小于外半径 {r_out}")
        EA += np.pi * E_z * (r_out**2 - r_in**2)
        EI += (np.pi / 4) * E_z * (r_out**4 - r_in**4)

    if not layers:
        raise ValueError("至少需要一层")

    r0 = layers[0]['r_in']          # 最内层内半径
    rn = layers[-1]['r_out']        # 最外层外半径
    R = (r0 + rn) / 2               # 中面半径
    # 对径集中力压扁刚度
    Kp = EI / (R**3 * (np.pi/2 - 4/np.pi))

    return EA, EI, Kp

# ==================== 默认示例数据 ====================
default_layers = [
    {'r_in': 0.40, 'r_out': 0.45, 'E_z': 500},   # PTFE
    {'r_in': 0.45, 'r_out': 0.50, 'E_z': 2500},  # 编织层（等效）
    {'r_in': 0.50, 'r_out': 0.60, 'E_z': 30},    # Pebax
]

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

# ==================== 初始化 session_state ====================
if 'layers' not in st.session_state:
    st.session_state.layers = default_layers.copy()
if 'num_layers' not in st.session_state:
    st.session_state.num_layers = len(default_layers)

# ==================== 侧边栏输入 ====================
with st.sidebar:
    st.header("导管几何参数")
    num_layers = st.number_input("总层数", min_value=1, max_value=10,
                                 value=st.session_state.num_layers, step=1,
                                 key="num_layers_input")
    st.session_state.num_layers = num_layers

    layers = []
    valid = True
    error_msg = ""

    for i in range(num_layers):
        with st.expander(f"第 {i+1} 层", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            with col1:
                r_in = st.number_input(f"内半径 r{i} (mm)",
                                       value=st.session_state.layers[i]['r_in'] if i < len(st.session_state.layers) else 0.0,
                                       step=0.01, format="%.3f", key=f"rin_{i}")
            with col2:
                r_out = st.number_input(f"外半径 r{i+1} (mm)",
                                        value=st.session_state.layers[i]['r_out'] if i < len(st.session_state.layers) else r_in + 0.05,
                                        step=0.01, format="%.3f", key=f"rout_{i}")

            # 层类型选择
            layer_type = st.radio(f"第 {i+1} 层类型", ["普通材料", "编织层"],
                                  horizontal=True, key=f"type_{i}",
                                  index=0 if i != 1 else 1)  # 默认第二层为编织层示例

            if layer_type == "普通材料":
                mat_name = st.selectbox(f"材料", list(material_library.keys()),
                                        key=f"mat_{i}",
                                        index=0 if i != 0 else 1)  # 默认第一层PTFE
                default_E = material_library[mat_name] if mat_name != "自定义" else 0
                E_z = st.number_input(f"轴向弹性模量 E_z (MPa)",
                                      value=float(default_E) if default_E is not None else 0.0,
                                      step=100.0, format="%.1f", key=f"Ez_{i}")
            else:
                st.markdown("**编织层参数**")
                col3, col4 = st.columns(2)
                with col3:
                    d_w = st.number_input(f"丝径 (mm)", value=0.02, step=0.005, format="%.3f", key=f"dw_{i}")
                    alpha = st.number_input(f"编织角 (度)", value=45.0, step=1.0, key=f"alpha_{i}")
                with col4:
                    PPI = st.number_input(f"PPI (1/in)", value=80, step=5, key=f"ppi_{i}")
                    E_f = st.number_input(f"丝材模量 (MPa)", value=200000, step=1000, key=f"Ef_{i}")
                E_m = st.number_input(f"基体模量 (MPa)", value=30, step=1, key=f"Em_{i}")

                # 计算编织层等效轴向模量（简化模型）
                # 体积分数近似：Vf = (π * d_w^2 * PPI) / (25.4 * 2 * (r_out^2 - r_in^2) * cos(α))
                # 注意：这是一个简化估算，实际更复杂。
                alpha_rad = np.radians(alpha)
                denom = 25.4 * 2 * (r_out**2 - r_in**2) * np.cos(alpha_rad)
                if denom > 0 and r_out > r_in:
                    V_f = min(1.0, (np.pi * d_w**2 * PPI) / denom)
                else:
                    V_f = 0.0
                    st.warning("无法计算编织体积分数，请检查半径和编织参数。")
                E_z = E_f * V_f * (np.cos(alpha_rad)**4) + E_m * (1 - V_f)
                st.success(f"计算得到等效轴向模量 E_z = {E_z:.1f} MPa")

            # 检查半径递增
            if i > 0:
                prev_r_out = layers[-1]['r_out']
                if r_in != prev_r_out:
                    st.warning(f"第 {i+1} 层内半径 ({r_in}) 与上一层外半径 ({prev_r_out}) 不一致，可能导致计算不准确。")
            if r_out <= r_in:
                valid = False
                error_msg = f"第 {i+1} 层外半径必须大于内半径"

            layers.append({'r_in': r_in, 'r_out': r_out, 'E_z': E_z})

    # 更新session_state
    st.session_state.layers = layers

    # 使用示例数据按钮
    if st.button("恢复示例数据"):
        st.session_state.layers = default_layers.copy()
        st.session_state.num_layers = len(default_layers)
        st.rerun()

# ==================== 主区域 ====================
st.header("微导管多层刚度计算结果")

if not valid:
    st.error(error_msg)
else:
    try:
        EA, EI, Kp = compute_stiffnesses(st.session_state.layers)
    except Exception as e:
        st.error(f"计算错误：{e}")
        st.stop()

    # 显示三个指标
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("轴向刚度 EA", f"{EA:.2f} N")
    with col2:
        st.metric("弯曲刚度 EI", f"{EI:.2f} N·mm²")
    with col3:
        st.metric("抗压扁刚度 Kp", f"{Kp:.2f} N/mm")

    # 绘制截面图
    st.subheader("导管截面示意图")
    fig, ax = plt.subplots(figsize=(5, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.layers)))
    # 从内到外画圆环
    for i, layer in enumerate(st.session_state.layers):
        r_in = layer['r_in']
        r_out = layer['r_out']
        # 画填充环
        ring = plt.Circle((0, 0), r_out, color=colors[i], alpha=0.5)
        ax.add_patch(ring)
        ring_in = plt.Circle((0, 0), r_in, color='white', alpha=1.0)
        ax.add_patch(ring_in)
        # 标注
        r_mid = (r_in + r_out) / 2
        ax.text(0, r_mid, f"Layer {i+1}\n{r_in:.2f}-{r_out:.2f} mm",
                ha='center', va='center', fontsize=8,
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    # 画最内腔
    inner_circle = plt.Circle((0, 0), st.session_state.layers[0]['r_in'],
                              color='white', fill=True, linewidth=0.5)
    ax.add_patch(inner_circle)
    ax.set_xlim(-st.session_state.layers[-1]['r_out']*1.1, st.session_state.layers[-1]['r_out']*1.1)
    ax.set_ylim(-st.session_state.layers[-1]['r_out']*1.1, st.session_state.layers[-1]['r_out']*1.1)
    ax.set_aspect('equal')
    ax.axis('off')
    st.pyplot(fig)

    # 显示层参数表
    st.subheader("当前层参数")
    df = pd.DataFrame(st.session_state.layers)
    df.index = df.index + 1
    df.index.name = "层号"
    st.dataframe(df)
