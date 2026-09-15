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
    if st.button("恢复示例数据"):
        st.session_state.structure = create_default_structure(L_total)
        st.session_state.x_pos = 0.0
        st.rerun()
