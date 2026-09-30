
把这个比例填到侧边栏的"EA 修正系数"里。

### 关于大变形

实验的下压量（比如 5 mm）通常**远超弹性段**。
工具的弹性公式只在小变形下准确，超过屈服点后会高估。

用"三点弯曲弹性段计算器"：
- 输入下压量
- 查看弹性段预测力
- 查看屈服点位移 δy（判断是否超出弹性段）

### 位移截距 + 力截距

修正实验曲线的零点偏移：

- 位移截距：曲线起点偏离原点的位移量
- 力截距：曲线起点偏离原点的力量

填入侧边栏后，弯曲屈服表的"预计实验读数"会同步修正。

## 11.5 保守默认值

| 系数 | 保守值 |
|---|---|
| EA 修正 | 0.6 |
| Kp 修正 | 0.4（薄壁）/ 0.6（厚壁） |
| 粘接系数 η | 0.8 |
| 软化系数 c | 1.0 |
| 编织层压扁折减 | 0.7 |
| 跨距 L | 30 mm |
    """)

with st.expander("12. 多方案对比", expanded=False):
    st.markdown("""
保存、载入、删除方案。方案是快照。

所有曲线图自动叠加显示所有方案。
    """)

with st.expander("13. 导出功能", expanded=False):
    st.markdown("""
| 按钮 | 内容 | 格式 |
|---|---|---|
| 当前截面参数表 | 当前 x 位置所有层参数 | CSV |
| 沿长度曲线数据 | 200 个采样点的六条曲线 | CSV |
| 完整报告 | 多 sheet 完整报告 | Excel |
| 导出模型参数 | 层结构 + 修正系数 + 已保存方案 + 自定义材料 + 三点弯曲截距 | JSON |
| 导入模型参数 | 从 JSON 恢复（上传 或 粘贴） | JSON |

**兼容性**：旧版本的 JSON 文件也能导入，缺失的字段自动用默认值。
    """)

with st.expander("14. 常见问题", expanded=False):
    st.markdown("""
**Q1：算出来 Kp 太大？**
A：Kp 是线性小变形刚度，薄壁需乘 0.3~0.5，厚壁需乘 0.6~0.8。

**Q2：为什么改了模量，Fu 没变？**
A：Fu 只取决于抗拉强度。

**Q3：编织层压扁折减怎么用？**
A：默认 1.0。已知编织层为网眼结构时可用 0.7~0.9。

**Q4：改了参数图表没更新？**
A：在 data_editor 里按 Ctrl+Enter 或点击表格外部提交。

**Q5：Excel 导出报错？**
A：需要安装 openpyxl。

**Q6：怎么把模型带到另一台电脑？**
A：导出 JSON → 在新环境导入。

**Q7：粘贴文本方式怎么用？**
A：用记事本打开导出的 JSON，全选复制，选择"📝 粘贴文本"，粘贴即可。

**Q8：材料库可以自己加材料吗？**
A：可以。侧边栏"📚 材料库管理"里添加。

**Q9：三点弯曲的位移截距和力截距是什么？**
A：用来修正实验曲线的零点偏移。

**Q10：三点弯曲力为什么偏大？**
A：工具的 My 是纯弹性理论值，忽略了 Brazier 椭圆化、σ_uts 偏差、层间滑移等，
实际力可能只有工具值的 30%~60%。工具值应视为"理想上限"。

**Q11：实验下压 5mm 怎么和工具对应？**
A：用"三点弯曲弹性段计算器"输入 5mm 看弹性预测力，
然后判断 δy（屈服点位移）是否小于 5mm——
如果小于，说明 5mm 已超出弹性段，工具会高估。
实际对比应以弹性段斜率反推的 EI 为准。

**Q12：EI 怎么转成 N？**
A：不能直接转。要指定加载条件（跨距、位移、曲率）。详见第 3 节。

**Q13：旧版本的 JSON 文件能导入吗？**
A：可以。旧文件缺字段自动用默认值，不报错。
    """)

with st.expander("15. 物理背景与局限", expanded=False):
    st.markdown("""
**理论模型**：多层同心圆管、完全粘接、材料线弹性、小变形、Timoshenko 薄环理论。

**主要简化**：忽略材料非线性、层间滑移、截面椭圆化、剪切变形、屈曲。

**薄壁 vs 厚壁的准确性**：
- 薄壁（t/R < 0.1）：EA 可信，EI 大曲率下高估，Fu_y / Fc 高估 2~3 倍
- 厚壁（t/R > 0.2）：EA/EI/Fu_y/My 较可信，Kp 需 × 0.6~0.8

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
    'name': 'Current', 'xs': xs,
    'EA': EA_arr, 'EI': EI_arr, 'Kp': Kp_arr,
    'Fu': Fu_arr, 'My': My_arr, 'Fc': Fc_arr,
    'is_current': True,
    'params': {'name': 'Current', 'structure': structure, 'L_total': L_total,
               'ea_correction': ea_correction, 'kp_correction': kp_correction,
               'eta_bond': eta_bond, 'softening_c': softening_c,
               'span_L': L_span, 'braid_crush_factor': braid_crush_factor}
})

for s in saved_schemes:
    try:
        s_braid_crush = s.get('braid_crush_factor', 1.0)
        s_xs, s_EA, s_EI, s_Kp, s_Fu, s_My, s_Fc = compute_along_length(
            s['structure'], s['L_total'], s['ea_correction'], s['kp_correction'],
            s['eta_bond'], s_braid_crush)
        all_schemes.append({
            'name': s['name'], 'xs': s_xs,
            'EA': s_EA, 'EI': s_EI, 'Kp': s_Kp,
            'Fu': s_Fu, 'My': s_My, 'Fc': s_Fc,
            'is_current': False, 'params': s})
    except Exception as e:
        st.warning(f"方案 '{s['name']}' 计算失败：{e}")

scheme_colors = plt.cm.tab10(np.linspace(0, 1, max(len(all_schemes), 1)))
layers = compute_at_x(structure, x_pos, eta_bond=eta_bond, braid_crush_factor=braid_crush_factor)

def make_label(sch):
    p = sch['params']
    kp_c = p['kp_correction']; c_v = p['softening_c']
    if sch['is_current']:
        return f"Current (Kp_corr={kp_c:.2f}, c={c_v:.2f})"
    return f"{sch['name']} (Kp_corr={kp_c:.2f}, c={c_v:.2f})"

# ============================================================
# 第一部分：刚度分析
# ============================================================
st.markdown("## 一、刚度分析")
st.caption("刚度描述导管抵抗变形的能力。单位：EA (N)、EI (N·mm²)、Kp (N/mm)。")

if not layers:
    st.warning("该位置没有有效的层数据。")
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
    st.caption(f"当前截面 t/R = **{tr_disp:.3f}** | const_eff = **{const_eff_disp:.4f}** | 模型：**{model_used}**")

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
    axes_s[0].set_ylabel('Axial Stiffness EA (N)'); axes_s[0].set_title('Axial Stiffness')
    axes_s[0].grid(True); axes_s[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[0].legend(loc='best', fontsize=8)
    axes_s[1].set_ylabel('Bending Stiffness EI (N·mm²)'); axes_s[1].set_title('Bending Stiffness')
    axes_s[1].grid(True); axes_s[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[1].legend(loc='best', fontsize=8)
    axes_s[2].set_ylabel('Crush Stiffness Kp (N/mm)'); axes_s[2].set_xlabel('Axial position (mm)')
    axes_s[2].set_title(f'Crush Stiffness (correction × {kp_correction:.3f})')
    axes_s[2].grid(True); axes_s[2].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_s[2].legend(loc='best', fontsize=8)
    fig_s.tight_layout(rect=[0, 0, 1, 0.96])
    st.pyplot(fig_s)

    st.subheader("抗压扁力-位移曲线（非线性）")
    r_outer_max = max(l['r_out'] for l in layers)
    D_outer = 2 * r_outer_max
    dD_max = 2.0
    dD_range = np.linspace(0, dD_max, 300)
    F_linear = Kp * dD_range
    F_nonlinear = compute_crush_force_nonlinear(Kp, D_outer, dD_range, softening_c)
    fig_cd, ax_cd = plt.subplots(figsize=(10, 6))
    for si, sch in enumerate(all_schemes):
        if sch['is_current']: continue
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
                s_F_nl = compute_crush_force_nonlinear(s_Kp_val, s_D_outer, dD_range, s_c)
                ax_cd.plot(dD_range, s_F_nl, color=scheme_colors[si],
                           linewidth=1.5, linestyle='--',
                           label=f"{sch['name']} (Kp={s_Kp_val:.2f}, c={s_c:.2f})")
        except Exception:
            pass
    ax_cd.plot(dD_range, F_linear, '--', color='gray', linewidth=1.8,
               label=f"Current: Linear (Kp={Kp:.2f})")
    ax_cd.plot(dD_range, F_nonlinear, 'r-', linewidth=2.5,
               label=f"Current: Non-linear (Kp={Kp:.2f}, c={softening_c:.2f})")
    ax_cd.set_xlabel('Diameter reduction ΔD (mm)')
    ax_cd.set_ylabel('Radial force F (N)')
    ax_cd.set_title('Crush Force–Displacement Curve')
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
        table_rows.append({'ΔD (mm)': f"{dD_v:.1f}",
                           'ΔD / 外径': f"{dD_v / D_outer * 100:.1f}%" if D_outer > 0 else "—",
                           '线性 F (N)': f"{F_lin:.4f}",
                           '非线性 F (N)': f"{F_nl:.4f}",
                           '软化幅度': f"-{delta_pct:.1f}%"})
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
                    compare_rows.append({
                        '方案': sch['name'] + (' (当前)' if sch['is_current'] else ''),
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
                        '压扁屈服力 Fc (N)': f"{s_Fc_x:.2f}"})
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
    axes_cb[0].bar(labels, ea_pct, color=colors); axes_cb[0].set_title('Axial (EA)')
    axes_cb[0].set_ylabel('Contribution (%)'); axes_cb[0].grid(axis='y', linestyle='--', alpha=0.6)
    axes_cb[1].bar(labels, ei_pct, color=colors); axes_cb[1].set_title('Bending (EI)')
    axes_cb[1].set_ylabel('Contribution (%)'); axes_cb[1].grid(axis='y', linestyle='--', alpha=0.6)
    axes_cb[2].bar(labels, kp_pct, color=colors); axes_cb[2].set_title(f'Crush (Kp) - {model_used}')
    axes_cb[2].set_ylabel('Contribution (%)'); axes_cb[2].grid(axis='y', linestyle='--', alpha=0.6)
    fig_cb.tight_layout(rect=[0, 0, 1, 0.95])
    st.pyplot(fig_cb)

    st.markdown("**各层刚度贡献明细**")
    stiff_rows = []
    for i, l in enumerate(layers):
        stiff_rows.append({
            "层": l['name'], "类型": l['type'],
            "EA 贡献 (N)": f"{EA_c[i] * ea_correction:.4f}",
            "EA 占比 (%)": f"{ea_pct[i]:.2f}%",
            "EI 贡献 (N·mm²)": f"{EI_c[i]:.4f}",
            "EI 占比 (%)": f"{ei_pct[i]:.2f}%",
            "Kp 贡献 (N/mm)": f"{Kp_c[i]:.4f}",
            "Kp 占比 (%)": f"{kp_pct[i]:.2f}%"})
    stiff_rows.append({"层": "合计", "类型": "",
                       "EA 贡献 (N)": f"{EA:.4f}", "EA 占比 (%)": "100.00%",
                       "EI 贡献 (N·mm²)": f"{EI:.4f}", "EI 占比 (%)": "100.00%",
                       "Kp 贡献 (N/mm)": f"{Kp:.4f}", "Kp 占比 (%)": "100.00%"})
    st.dataframe(pd.DataFrame(stiff_rows), use_container_width=True, hide_index=True)

    filler_names = [l['name'] for l in layers if l.get('is_filler', False)]
    if filler_names:
        st.info(f"当前段缺失的层已自动用热熔材料填充：{', '.join(filler_names)}。")

    if thick_ratio < 0.08:
        st.info(f"t/R = **{thick_ratio:.3f}** < 0.08（薄壁）。模型：**{model_used}**。")
    elif thick_ratio < 0.15:
        st.warning(f"t/R = **{thick_ratio:.3f}** ∈ [0.08, 0.15)（过渡区）。模型：**{model_used}**。")
    elif thick_ratio < 0.5:
        st.info(f"t/R = **{thick_ratio:.3f}** ∈ [0.15, 0.5)（厚壁）。模型：**{model_used}**。")
    else:
        st.warning(f"t/R = **{thick_ratio:.3f}** ≥ 0.5（极厚壁）。模型：**{model_used}**。")

# ============================================================
# 第二部分：强度分析
# ============================================================
st.markdown("---")
st.markdown("## 二、强度分析")
st.caption(f"弯曲按三点弯曲换算，跨距 L = {L_span:.1f} mm，位移截距 = {tp_offset_mm:.2f} mm，力截距 = {tp_offset_N:.2f} N。")

if layers:
    Fu, Fu_layer = compute_axial_strength(layers)
    Fu_y, ax_yield_ctrl, ax_yield_cands, ax_yield_contribs = compute_axial_yield(layers, ea_correction)
    My, bending_ctrl, bending_cands, bending_contribs = compute_bending_yield(layers)
    Fc, collapse_ctrl, collapse_cands, collapse_contribs = compute_collapse_force(layers)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("拉伸极限 Fu (N)", f"{Fu:.2f}")
    c2.metric("拉伸起始屈服 Fu_y (N)", f"{Fu_y:.2f}")
    c3.metric("弯曲屈服力矩 My (N·mm)", f"{My:.4f}")
    c4.metric("压扁屈服力 Fc (N)", f"{Fc:.2f}")

    ctrl_info = []
    if ax_yield_ctrl: ctrl_info.append(f"**拉伸屈服控制层**：{ax_yield_ctrl}")
    if bending_ctrl: ctrl_info.append(f"**弯曲屈服控制层**：{bending_ctrl}")
    if collapse_ctrl: ctrl_info.append(f"**压扁屈服控制层**：{collapse_ctrl}")
    if ctrl_info:
        st.info("。".join(ctrl_info) + "。")
    else:
        st.warning("没有层满足强度分析条件（需 σ_uts > 0 且 E > 0）。")

    st.subheader("拉伸起始屈服 — 各层贡献")
    ax_rows = []
    for contrib in ax_yield_contribs:
        is_valid = contrib.get('is_valid', True)
        col_yf = f"{Fu_y:.4f}" if is_valid else "—"
        col_flag = ("★" if contrib['is_ctrl'] else "") if is_valid else "— (σ≤0 跳过)"
        ax_rows.append({"层": contrib['layer'],
                        "轴向模量 (MPa)": f"{contrib['E_z']:.1f}",
                        "抗拉强度 (MPa)": f"{contrib['sigma_uts']:.1f}",
                        "屈服应变": f"{contrib['eps_y']*100:.2f}%" if contrib['E_z'] > 0 and contrib['sigma_uts'] > 0 else "—",
                        "该层屈服时整体拉力 (N)": col_yf,
                        "整体屈服时该层承担拉力 (N)": f"{contrib['F_i']:.4f}",
                        "占比 (%)": f"{contrib['pct']:.2f}%",
                        "是否控制层": col_flag})
    st.dataframe(pd.DataFrame(ax_rows), use_container_width=True)

    st.subheader("弯曲屈服 — 各层贡献")
    b_ctrl_dict = {c['layer']: c for c in bending_cands}
    b_rows = []
    for contrib in bending_contribs:
        layer_name = contrib['layer']
        cand = b_ctrl_dict.get(layer_name, {})
        is_valid = contrib.get('is_valid', True)
        if is_valid:
            col_My = f"{cand.get('M_y', 0):.4f}"
            col_flag = "★" if contrib['is_ctrl'] else ""
            Fy_3p = 4 * cand.get('M_y', 0) / L_span if L_span > 0 else 0.0
            col_Fy_3p = f"{Fy_3p:.4f}"
            col_Fy_actual = f"{Fy_3p + tp_offset_N:.4f}"
        else:
            col_My = "—"; col_flag = "— (σ≤0 跳过)"
            col_Fy_3p = "—"; col_Fy_actual = "—"
        b_rows.append({"层": layer_name,
                       "轴向模量 (MPa)": f"{cand.get('E_z', 0):.1f}" if cand else "—",
                       "外半径 (mm)": f"{cand.get('r_out', 0):.4f}" if cand else "—",
                       "抗拉强度 (MPa)": f"{cand.get('sigma_uts', 0):.1f}",
                       "该层屈服时整体弯矩 (N·mm)": col_My,
                       "整体屈服时该层承担弯矩 (N·mm)": f"{contrib['M_actual']:.4f}",
                       "占比 (%)": f"{contrib['pct']:.2f}%",
                       "是否控制层": col_flag,
                       f"三点弯曲力 (N, L={L_span:.0f}mm)": col_Fy_3p,
                       "预计实验读数 (N)": col_Fy_actual})
    st.dataframe(pd.DataFrame(b_rows), use_container_width=True)

    # ============================================================
    # 三点弯曲弹性段计算器（v50 新增）
    # ============================================================
    st.subheader("📐 三点弯曲弹性段计算器")
    st.caption(
        "输入一个下压距离，计算弹性段对应的力。"
        "公式：F = 48 · EI · δ / L³。超出屈服点后弹性公式会高估。"
    )

    col_d1, col_d2 = st.columns([1, 3])
    with col_d1:
        tp_delta = st.number_input(
            "下压距离 δ (mm)",
            min_value=0.0, max_value=100.0,
            value=float(st.session_state.tp_delta_input),
            step=0.1, format="%.2f",
            key="tp_delta_input_widget",
            help="输入实验的下压量，比如 0.1、0.5、1.0、5.0 等"
        )
    st.session_state.tp_delta_input = tp_delta

    if L_span > 0 and EI > 0:
        # 弹性段斜率 k = 48·EI/L³
        k_elastic = 48.0 * EI / (L_span ** 3)
        # 弹性段在该下压量下的力
        F_elastic = k_elastic * tp_delta
        # 屈服点力（取弯曲屈服，与跨距换算）
        Fy_yield = 4.0 * My / L_span if L_span > 0 else 0.0
        # 屈服点位移（估算）
        delta_yield = Fy_yield / k_elastic if k_elastic > 0 else 0.0

        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("弹性段斜率 k (N/mm)", f"{k_elastic:.4f}")
        cc2.metric(f"δ = {tp_delta:.2f} mm 时的弹性力 (N)", f"{F_elastic:.4f}")
        cc3.metric("屈服点力 Fy (N)", f"{Fy_yield:.4f}")
        cc4.metric("屈服点位移 δy (mm)", f"{delta_yield:.4f}")

        # 状态判断
        if delta_yield > 0:
            ratio = tp_delta / delta_yield
            if ratio < 0.8:
                st.success(
                    f"✅ **弹性段**：δ = {tp_delta:.2f} mm，约为屈服点位移 {delta_yield:.3f} mm 的 {ratio*100:.0f}%。"
                    f"弹性公式可信。"
                )
            elif ratio < 1.2:
                st.warning(
                    f"⚠️ **接近屈服点**：δ = {tp_delta:.2f} mm，约为屈服点位移 {delta_yield:.3f} mm 的 {ratio*100:.0f}%。"
                    f"弹性公式开始有偏差。"
                )
            else:
                st.error(
                    f"❌ **超出弹性段**：δ = {tp_delta:.2f} mm，是屈服点位移 {delta_yield:.3f} mm 的 {ratio*100:.0f} 倍。"
                    f"弹性公式严重高估，实际力会因 Brazier 椭圆化和压扁而明显低于 {F_elastic:.3f} N。"
                )

        # 附加：多下压量对比表
        st.markdown("**多下压量对比**")
        compare_deltas = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        dd_rows = []
        for d_v in compare_deltas:
            F_el = k_elastic * d_v
            status = "弹性段" if (delta_yield > 0 and d_v < 0.8 * delta_yield) else \
                     ("接近屈服" if (delta_yield > 0 and d_v < 1.2 * delta_yield) else "大变形")
            dd_rows.append({
                "δ (mm)": f"{d_v:.2f}",
                "弹性力 F_elastic (N)": f"{F_el:.4f}",
                "相对屈服点": f"{d_v / delta_yield * 100:.0f}%" if delta_yield > 0 else "—",
                "状态": status
            })
        st.dataframe(pd.DataFrame(dd_rows), use_container_width=True, hide_index=True)

        st.caption(
            f"注：弹性段斜率 k 由工具计算的弯曲刚度 EI 决定（EI = {EI:.2f} N·mm²）。"
            f"如果实验测到的斜率低于 k_elastic，说明实际 EI 偏低，"
            f"可以把 EA 修正系数调为 k_实测 / k_elastic。"
        )
    else:
        st.info("当前截面 EI 或跨距无效，无法计算弹性段。")

    st.subheader("压扁屈服 — 各层贡献")
    c_ctrl_dict = {c['layer']: c for c in collapse_cands}
    c_rows = []
    for contrib in collapse_contribs:
        layer_name = contrib['layer']
        cand = c_ctrl_dict.get(layer_name, {})
        is_valid = contrib.get('is_valid', True)
        if is_valid:
            col_Fc = f"{cand.get('F_c', 0):.4f}"
            col_flag = "★" if contrib['is_ctrl'] else ""
            E_theta_v = cand.get('E_theta', 0); sigma_v = cand.get('sigma_uts', 0)
            col_eps = f"{sigma_v / E_theta_v * 100:.2f}%" if E_theta_v > 0 and sigma_v > 0 else "—"
        else:
            col_Fc = "—"; col_flag = "— (σ≤0 跳过)"; col_eps = "—"
        c_rows.append({"层": layer_name,
                       "环向模量 (MPa)": f"{cand.get('E_theta', 0):.1f}" if cand else "—",
                       "壁厚 (mm)": f"{cand.get('t', 0):.4f}" if cand else "—",
                       "抗拉强度 (MPa)": f"{cand.get('sigma_uts', 0):.1f}",
                       "屈服应变": col_eps,
                       "该层屈服时整体受力 (N)": col_Fc,
                       "整体屈服时该层承担弯矩 (N·mm)": f"{contrib['M_actual']:.4f}",
                       "占比 (%)": f"{contrib['pct']:.2f}%",
                       "是否控制层": col_flag})
    st.dataframe(pd.DataFrame(c_rows), use_container_width=True)

    st.subheader("轴向拉力（整体极限） — 各层贡献")
    fu_rows = []
    for i, l in enumerate(layers):
        if l['type'] == '弹簧圈': method = "弹簧公式 + 热熔填充"
        elif l['type'] == '编织层': method = "丝材 + 热熔填充"
        elif l.get('is_filler', False): method = "填充层 (σ·A)"
        else: method = "σ·A"
        fu_rows.append({"层": l['name'], "类型": l['type'], "计算方法": method,
                        "抗拉强度 (MPa)": f"{l['sigma_uts']:.1f}",
                        "丝材/弹簧贡献 (N)": f"{l.get('Fu_fiber', 0.0):.4f}",
                        "热熔填充贡献 (N)": f"{l.get('Fu_matrix', 0.0):.4f}",
                        "合计 (N)": f"{Fu_layer[i]:.4f}"})
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
    axes_t[0].set_ylabel('Axial Tensile Force Fu (N)'); axes_t[0].set_title('Max Axial Tensile Force')
    axes_t[0].grid(True); axes_t[0].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[0].legend(loc='best', fontsize=8)
    axes_t[1].set_ylabel('Bending Yield Moment My (N·mm)'); axes_t[1].set_title('Bending Yield Moment')
    axes_t[1].grid(True); axes_t[1].axvline(x=x_pos, color='gray', linestyle='--', alpha=0.5)
    axes_t[1].legend(loc='best', fontsize=8)
    axes_t[2].set_ylabel('Collapse Force Fc (N)'); axes_t[2].set_xlabel('Axial position (mm)')
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
        row = {"层": l['name'], "类型": l['type'],
               "内半径 (mm)": f"{l['r_in']:.4f}", "外半径 (mm)": f"{l['r_out']:.4f}",
               "轴向模量 (MPa)": f"{l['E_z']:.2f}", "环向模量 (MPa)": f"{l['E_theta']:.2f}",
               "抗拉强度 (MPa)": f"{l['sigma_uts']:.1f}"}
        row["丝材体积分数 (%)"] = f"{l['V_f']*100:.2f}%" if l['V_f'] is not None else "—"
        row["空隙体积分数 (%)"] = f"{l['V_void']*100:.2f}%" if l['V_void'] is not None else "—"
        param_rows.append(row)
    param_df = pd.DataFrame(param_rows)
    st.dataframe(param_df, use_container_width=True)
else:
    param_df = pd.DataFrame()

# ============================================================
# 导出
# ============================================================
st.markdown("---")
st.subheader("📥 导出结果")
exp_col1, exp_col2, exp_col3 = st.columns(3)

with exp_col1:
    if not param_df.empty:
        csv_bytes = param_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📄 当前截面参数表 (CSV)", data=csv_bytes,
                           file_name=f"cross_section_x{x_pos:.1f}mm.csv",
                           mime="text/csv", key="dl_param_csv")
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
        '压扁屈服力 Fc (N)': Fc_arr})
    curve_csv = curve_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📈 沿长度曲线数据 (CSV)", data=curve_csv,
                       file_name="along_length_curves.csv", mime="text/csv",
                       key="dl_curve_csv")

with exp_col3:
    if HAS_OPENPYXL:
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                overview_data = {
                    '参数': ['导管总长度 (mm)', '当前轴向位置 (mm)', 'EA 修正系数',
                             'Kp 修正系数', '粘接系数 η', '三点弯曲跨距 (mm)',
                             '软化系数 c', '编织层压扁折减系数',
                             '位移截距 (mm)', '力截距 (N)', '已保存方案数'],
                    '值': [L_total, x_pos, ea_correction, kp_correction, eta_bond, L_span,
                           softening_c, braid_crush_factor, tp_offset_mm, tp_offset_N,
                           len(saved_schemes)]}
                pd.DataFrame(overview_data).to_excel(writer, sheet_name='概览', index=False)

                if layers:
                    cur_metrics = {
                        '指标': ['轴向刚度 EA (N)', '弯曲刚度 EI (N·mm²)', '抗压扁刚度 Kp (N/mm)',
                                 '拉伸极限 Fu (N)', '拉伸起始屈服 Fu_y (N)',
                                 '弯曲屈服力矩 My (N·mm)', '压扁屈服力 Fc (N)',
                                 '壁厚半径比 t/R', '有效几何常数 const_eff'],
                        '值': [EA, EI, Kp, Fu, Fu_y, My, Fc, tr_disp, const_eff_disp]}
                    pd.DataFrame(cur_metrics).to_excel(writer, sheet_name='当前截面指标', index=False)

                    stiff_export_rows = []
                    for i, l in enumerate(layers):
                        stiff_export_rows.append({
                            "层": l['name'], "类型": l['type'],
                            "EA贡献_N": EA_c[i] * ea_correction, "EA占比_%": ea_pct[i],
                            "EI贡献_Nmm2": EI_c[i], "EI占比_%": ei_pct[i],
                            "Kp贡献_N_per_mm": Kp_c[i], "Kp占比_%": kp_pct[i]})
                    pd.DataFrame(stiff_export_rows).to_excel(writer, sheet_name='刚度各层贡献', index=False)

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
                            "是否控制层": "★" if contrib['is_ctrl'] else ("— (σ≤0 跳过)" if not is_valid else "")})
                    pd.DataFrame(ax_export_rows).to_excel(writer, sheet_name='拉伸起始屈服各层贡献', index=False)

                    bend_export_rows = []
                    for contrib in bending_contribs:
                        layer_name = contrib['layer']
                        cand = b_ctrl_dict.get(layer_name, {})
                        is_valid = contrib.get('is_valid', True)
                        M_y_v = cand.get('M_y', None) if is_valid else None
                        Fy_3p_v = (4 * M_y_v / L_span) if (is_valid and M_y_v is not None and L_span > 0) else None
                        Fy_actual_v = (Fy_3p_v + tp_offset_N) if Fy_3p_v is not None else None
                        bend_export_rows.append({
                            "层": layer_name,
                            "轴向模量_MPa": cand.get('E_z', None) if is_valid else None,
                            "外半径_mm": cand.get('r_out', None) if is_valid else None,
                            "抗拉强度_MPa": cand.get('sigma_uts', 0),
                            "该层屈服时整体弯矩_Nmm": M_y_v,
                            "整体屈服时该层承担弯矩_Nmm": contrib['M_actual'],
                            "三点弯曲力_N": Fy_3p_v,
                            "预计实验读数_N": Fy_actual_v,
                            "占比_%": contrib['pct'],
                            "是否控制层": "★" if contrib['is_ctrl'] else ("— (σ≤0 跳过)" if not is_valid else "")})
                    pd.DataFrame(bend_export_rows).to_excel(writer, sheet_name='弯曲屈服各层贡献', index=False)

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
                            "是否控制层": "★" if contrib['is_ctrl'] else ("— (σ≤0 跳过)" if not is_valid else "")})
                    pd.DataFrame(coll_export_rows).to_excel(writer, sheet_name='压扁屈服各层贡献', index=False)

                    fu_export_rows = []
                    for i, l in enumerate(layers):
                        fu_export_rows.append({
                            "层": l['name'], "类型": l['type'],
                            "抗拉强度_MPa": l['sigma_uts'],
                            "丝材_弹簧贡献_N": l.get('Fu_fiber', 0.0),
                            "热熔填充贡献_N": l.get('Fu_matrix', 0.0),
                            "合计_N": Fu_layer[i]})
                    pd.DataFrame(fu_export_rows).to_excel(writer, sheet_name='轴向拉力各层贡献', index=False)

                    dD_export = np.linspace(0, 2.0, 200)
                    F_lin_export = Kp * dD_export
                    F_nl_export = compute_crush_force_nonlinear(Kp, D_outer, dD_export, softening_c)
                    fd_df = pd.DataFrame({'ΔD 直径减小量 (mm)': dD_export,
                                          '线性力 F (N)': F_lin_export,
                                          '非线性力 F (N)': F_nl_export})
                    fd_df.to_excel(writer, sheet_name='力-位移曲线', index=False)

                    # 三点弯曲弹性段
                    if L_span > 0 and EI > 0:
                        k_el = 48.0 * EI / (L_span ** 3)
                        Fy_3p_cur = 4.0 * My / L_span
                        dY_el = Fy_3p_cur / k_el if k_el > 0 else 0.0
                        tp_rows = []
                        for d_v in [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]:
                            F_el_v = k_el * d_v
                            stat = "弹性段" if (dY_el > 0 and d_v < 0.8*dY_el) else \
                                   ("接近屈服" if (dY_el > 0 and d_v < 1.2*dY_el) else "大变形")
                            tp_rows.append({"δ (mm)": d_v,
                                            "弹性力 F (N)": F_el_v,
                                            "相对屈服点 (%)": (d_v/dY_el*100) if dY_el > 0 else None,
                                            "状态": stat})
                        pd.DataFrame(tp_rows).to_excel(writer, sheet_name='三点弯曲弹性段', index=False)

                if not param_df.empty:
                    param_df.to_excel(writer, sheet_name='当前截面参数', index=False)
                curve_df.to_excel(writer, sheet_name='沿长度曲线', index=False)

                if len(all_schemes) > 1:
                    compare_rows_export = []
                    for sch in all_schemes:
                        p = sch['params']
                        try:
                            s_braid_crush_e = p.get('braid_crush_factor', 1.0)
                            if sch['is_current']: s_layers_export = layers
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
                                    '压扁屈服力 Fc (N)': s_Fc_x})
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
            st.download_button("📊 完整报告 (Excel)", data=buffer.getvalue(),
                               file_name="catheter_analysis_report.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="dl_excel")
        except Exception as e:
            st.error(f"Excel 生成失败：{e}")
    else:
        st.button("📊 完整报告 (需 openpyxl)", disabled=True, key="dl_excel_disabled")
        st.caption("安装: pip install openpyxl")

st.caption("CSV 用 UTF-8 with BOM 编码，Excel 打开不会乱码。")
