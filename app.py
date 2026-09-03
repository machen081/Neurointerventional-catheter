import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from copy import deepcopy

st.set_page_config(page_title="微导管多层刚度沿长度分布计算器", layout="wide")

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
def compute_stiffness_at_x(layers):
    """根据给定位置的层参数计算 EA, EI, Kp"""
    EA = 0.0
    EI = 0.0
    for _, row in layers.iterrows():
        r_in = row['内半径 (mm)']
        r_out = row['外半径 (mm)']
        E_z = row['轴向模量 (MPa)']
        if r_out <= r_in:
            raise ValueError(f"层内外半径错误：内半径 {r_in} 不小于外半径 {r_out}")
        EA += np.pi * E_z * (r_out**2 - r_in**2)
        EI += (np.pi / 4) * E_z * (r_out**4 - r_in**4)
    if layers.empty:
        raise ValueError("至少需要一层")
    r0 = layers.iloc[0]['内半径 (mm)']
    rn = layers.iloc[-1]['外半径 (mm)']
    R = (r0 + rn) / 2
    Kp = EI / (R**3 * (np.pi/2 - 4/np.pi))
    return EA, EI, Kp

# ==================== 默认分段数据 ====================
def create_default_segment():
    layers_df = pd.DataFrame([
        {"层号": 1, "内半径 (mm)": 0.40, "外半径 (mm)": 0.45, "轴向模量 (MPa)": 500},
        {"层号": 2, "内半径 (mm)": 0.45, "外半径 (mm)": 0.50, "轴向模量 (MPa)": 2500},
        {"层号": 3, "内半径 (mm)": 0.50, "外半径 (mm)": 0.60, "轴向模量 (MPa)": 30},
    ])
    return layers_df

default_segments = [
    {"start": 0, "end": 100, "layers": create_default_segment()},
    {"start": 100, "end": 350, "layers": create_default_segment()},  # 实际可修改第二段半径不同
]

# ==================== session_state 初始化 ====================
if 'segments' not in st.session_state:
    st.session_state.segments = deepcopy(default_segments)
if 'L_total' not in st.session_state:
    st.session_state.L_total = 350.0

# ==================== 侧边栏 ====================
with st.sidebar:
    st.header("导管总长度")
    L_total = st.number_input("总长度 (mm)", min_value=1.0, value=st.session_state.L_total,
                              step=10.0, key="L_total_input")
    st.session_state.L_total = L_total

    st.header("分段管理")
    n_segments = st.number_input("分段数", min_value=1, max_value=20,
                                 value=len(st.session_state.segments), step=1,
                                 key="n_segments_input")
    # 调整分段数
    if n_segments != len(st.session_state.segments):
        if n_segments > len(st.session_state.segments):
            for _ in range(n_segments - len(st.session_state.segments)):
                last_seg = st.session_state.segments[-1]
                new_start = last_seg['end']
                new_end = min(new_start + 10.0, L_total)
                st.session_state.segments.append({
                    "start": new_start,
                    "end": new_end,
                    "layers": deepcopy(last_seg['layers'])
                })
        else:
            st.session_state.segments = st.session_state.segments[:n_segments]
        st.rerun()

    # 编辑每个分段
    segments_to_save = []
    valid = True
    for i, seg in enumerate(st.session_state.segments):
        with st.expander(f"分段 {i+1}", expanded=(i == 0)):
            col1, col2 = st.columns(2)
            with col1:
                start = st.number_input(f"起点 (mm)", value=float(seg['start']),
                                        step=1.0, key=f"seg_{i}_start")
            with col2:
                end = st.number_input(f"终点 (mm)", value=float(seg['end']),
                                      step=1.0, key=f"seg_{i}_end")
            if end <= start:
                st.error("终点必须大于起点")
                valid = False

            st.markdown("**该段的层参数**（可编辑，至少一层）")
            # 使用 data_editor 编辑层表
            layers_df = st.data_editor(
                seg['layers'],
                num_rows="dynamic",
                key=f"seg_{i}_layers_editor",
                use_container_width=True
            )
            if layers_df.empty:
                st.warning("至少需要一层")
                valid = False

            segments_to_save.append({
                "start": start,
                "end": end,
                "layers": layers_df
            })

    # 检查分段覆盖是否连续
    if valid and len(segments_to_save) > 0:
        # 按起点排序
        segments_to_save_sorted = sorted(segments_to_save, key=lambda x: x['start'])
        # 检查首尾相接
        if segments_to_save_sorted[0]['start'] > 0:
            st.warning(f"第一个分段起点应不小于0，当前为{segments_to_save_sorted[0]['start']}")
            valid = False
        for i in range(len(segments_to_save_sorted) - 1):
            if abs(segments_to_save_sorted[i]['end'] - segments_to_save_sorted[i+1]['start']) > 1e-6:
                st.warning(f"分段 {i+1} 终点 ({segments_to_save_sorted[i]['end']}) 与分段 {i+2} 起点 ({segments_to_save_sorted[i+1]['start']}) 不连续")
                valid = False
        if segments_to_save_sorted[-1]['end'] < L_total:
            st.warning(f"最后一个分段终点应不小于总长度 {L_total}，当前为{segments_to_save_sorted[-1]['end']}")
            valid = False

    # 保存按钮
    if st.button("保存修改", type="primary"):
        if valid:
            st.session_state.segments = segments_to_save
            st.success("参数已保存")
            st.rerun()
        else:
            st.error("请修正错误后再保存")

    # 恢复示例数据
    if st.button("恢复示例数据"):
        st.session_state.segments = deepcopy(default_segments)
        st.session_state.L_total = 350.0
        st.rerun()

# ==================== 主区域 ====================
st.header("刚度沿长度分布")

if not st.session_state.segments:
    st.info("请在左侧添加分段数据")
else:
    # 使用已保存的分段（如果点击了保存）或当前编辑中的分段
    # 注意：为了实时显示，我们可以使用未保存的segments_to_save，但需先验证有效性。
    # 简化：如果侧边栏有修改未保存，我们仍使用已保存的数据进行绘图，提示用户保存。
    plot_segments = st.session_state.segments

    # 生成 x 坐标
    x = np.linspace(0, st.session_state.L_total, 500)

    # 初始化结果数组
    EA_arr = np.zeros_like(x)
    EI_arr = np.zeros_like(x)
    Kp_arr = np.zeros_like(x)

    # 对于每个 x，找到所在分段并计算
    for i, xi in enumerate(x):
        # 找到包含 xi 的分段
        seg = None
        for s in plot_segments:
            if s['start'] <= xi < s['end']:
                seg = s
                break
        if seg is None:
            # 边界情况：x=0 或在最后一段终点
            if xi < plot_segments[0]['start']:
                seg = plot_segments[0]
            else:
                seg = plot_segments[-1]
        try:
            EA, EI, Kp = compute_stiffness_at_x(seg['layers'])
            EA_arr[i] = EA
            EI_arr[i] = EI
            Kp_arr[i] = Kp
        except Exception as e:
            st.error(f"在 x={xi:.2f} 处计算失败：{e}")
            st.stop()

    # 绘图
    fig, axes = plt.subplots(3, 1, figsize=(10, 12))
    fig.suptitle("微导管刚度沿长度分布")

    axes[0].plot(x, EA_arr, 'b-', linewidth=2)
    axes[0].set_ylabel('轴向刚度 EA (N)')
    axes[0].grid(True)
    axes[0].set_title('Axial Stiffness')

    axes[1].plot(x, EI_arr, 'g-', linewidth=2)
    axes[1].set_ylabel('弯曲刚度 EI (N·mm²)')
    axes[1].grid(True)
    axes[1].set_title('Bending Stiffness')

    axes[2].plot(x, Kp_arr, 'r-', linewidth=2)
    axes[2].set_xlabel('距远端位置 (mm)')
    axes[2].set_ylabel('抗压扁刚度 Kp (N/mm)')
    axes[2].grid(True)
    axes[2].set_title('Crush Stiffness (diametral compression)')

    st.pyplot(fig)

    # 显示分段数据表
    st.subheader("当前分段数据")
    for i, seg in enumerate(plot_segments):
        st.markdown(f"**分段 {i+1}：{seg['start']:.1f} – {seg['end']:.1f} mm**")
        st.dataframe(seg['layers'], use_container_width=True)
