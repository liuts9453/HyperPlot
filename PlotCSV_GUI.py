#!/home/liu/regular/bin/python
from tkinterdnd2 import DND_FILES, TkinterDnD
from tkinter import ttk, Menu, messagebox, simpledialog, Toplevel
import tkinter as tk
import HyperPlot
import os
import sys
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter.scrolledtext import ScrolledText


def treeview_to_dict(tree, parent=""):
    """将 Treeview 的内容转换为嵌套字典，使用文本作为键名。"""
    tree_dict = {}
    children = tree.get_children(parent)
    for child in children:
        text = tree.item(child, "text")  # 获取节点的文本作为键
        values = tree.item(child, "values")
        if tree.get_children(child):
            tree_dict[text] = treeview_to_dict(tree, child)
        else:
            tree_dict[text] = values[0] if values else None
    return tree_dict


class PrintRedirector:
    """用于将 print 输出重定向到消息区域"""

    def __init__(self, app_instance, fallback_stream):
        self.app_instance = app_instance
        self.fallback_stream = fallback_stream

    def write(self, message):
        """将消息写入到消息区域"""
        if not message.strip():  # 过滤掉空行
            return
        if not hasattr(self.app_instance, "message_box"):
            self.app_instance._pending_log_messages.append(message)
            self.fallback_stream.write(message)
            self.fallback_stream.flush()
            return
        try:
            self.app_instance.log_message(message)
        except Exception:
            self.fallback_stream.write(message)
            self.fallback_stream.flush()

    def flush(self):
        self.fallback_stream.flush()


class PlotApp:
    def __init__(self):
        self.plotter_properties = [
            "plot_type",
            "right_axis_color",
            "axis_labels",
            "loc",
            "plot_dpi",
            "legend_line_length",
            "label_decimal",
            "fig_width_cm",
            "fig_height_cm",
            "marks",
            "background_alpha",
            "background_points",
            "color_palette",
            "seperator",
            "xmin",
            "xmax",
            "grid",
        ]
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        self._pending_log_messages = []
        self._stdout_redirector = PrintRedirector(self, self._old_stdout)
        self._stderr_redirector = PrintRedirector(self, self._old_stderr)
        sys.stdout = self._stdout_redirector
        sys.stderr = self._stderr_redirector
        self.plotter = HyperPlot.HyperPlot()
        self.default_template_loaded = None
        self.default_template_error = None
        try:
            self.default_template_loaded = self.plotter.load_default_template()
        except Exception as e:
            self.default_template_error = str(e)
        self.root = TkinterDnD.Tk()
        self.root.title("CSVPlot GUI")
        self.root.geometry("1280x720")
        self._layout()
        self.flush_pending_logs()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        # 绑定全局左键点击事件，关闭所有菜单
        self.root.bind("<Button-1>", lambda _: self.close_all_menus())
        self.root.bind("<Button-3>", lambda _: self.close_all_menus())
        self.init_context_menus()
        self.generate_plot_view(self.plotter.get_plot(None, ""), self.preview_frame)
        if self.default_template_loaded:
            self.log_message(f"Default template loaded: {self.default_template_loaded}")
        elif self.default_template_error:
            self.log_message(
                f"Default template could not be loaded: {self.default_template_error}"
            )
        # 注册拖拽事件
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.on_file_drop)

    def preserve_listbox_selection(method):
        """修饰器：在执行 method 之前记住 Listbox 的选中索引，并在结束后恢复。"""

        def wrapper(self, *args, **kwargs):
            # 1. 记住当前 Listbox 的选中状态
            old_selection = self.selection_list.curselection()

            # 2. 执行原方法
            result = method(self, *args, **kwargs)

            # 3. 更新 Listbox 并恢复选中状态
            self.update_selection_list()  # 先更新列表
            for idx in old_selection:
                self.selection_list.selection_set(idx)  # 恢复选中状态

            return result

        return wrapper

    def _layout(self):
        # 配置根窗口网格：3:2 比例
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)
        # ------------------------ 左侧 ------------------------ #
        self.left_frame = tk.Frame(self.root, bd=2)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=1, pady=2)
        self.left_frame.grid_rowconfigure(1, weight=1)  # 使 Listbox 垂直可扩展
        self.left_frame.grid_columnconfigure(0, weight=1)  # 水平可扩展
        self.workbench_header_frame = tk.Frame(self.left_frame)
        self.workbench_header_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=0)
        self.workbench_header_frame.grid_columnconfigure(0, weight=1)
        self.selection_label = tk.Label(
            self.workbench_header_frame,
            text="Workbench",
            fg="black",
            font=("Serif", 12, "bold"),
        )
        self.selection_label.grid(row=0, column=0, sticky="w", padx=0, pady=0)
        self.select_all_button = ttk.Button(
            self.workbench_header_frame,
            text="All",
            width=6,
            command=self.toggle_select_all,
        )
        self.select_all_button.grid(row=0, column=1, sticky="e", padx=1, pady=0)
        self.invert_selection_button = ttk.Button(
            self.workbench_header_frame,
            text="Invert",
            width=7,
            command=self.invert_selection,
        )
        self.invert_selection_button.grid(row=0, column=2, sticky="e", padx=1, pady=0)

        self.selection_list = tk.Listbox(
            self.left_frame, selectmode="multiple", exportselection=False
        )
        self.selection_list.grid(row=1, column=0, sticky="nsew", padx=2, pady=0)

        self.legends_label = tk.Label(self.left_frame, text="Batch Style:", fg="black")
        self.legends_label.grid(row=2, column=0, sticky="w", padx=2, pady=0)

        self.legends_input = tk.Entry(self.left_frame)
        self.legends_input.grid(row=3, column=0, sticky="ew", padx=2, pady=0)

        self.palette_label = tk.Label(self.left_frame, text="Palette:", fg="black")
        self.palette_label.grid(row=4, column=0, sticky="w", padx=2, pady=0)
        self.palette_frame = tk.Frame(self.left_frame)
        self.palette_frame.grid(row=5, column=0, sticky="ew", padx=2, pady=0)

        self.fastcsv_var = tk.BooleanVar()
        self.fastcsv_switch = ttk.Checkbutton(
            self.left_frame, text="fastCSV", variable=self.fastcsv_var
        )
        self.fastcsv_switch.grid(row=6, column=0, sticky="w", padx=2, pady=0)
        self.tool_frame = tk.Frame(self.left_frame)
        self.tool_frame.grid_configure(row=1, column=3)
        self.tool_frame.grid(row=7, column=0, sticky="ew", padx=2, pady=0)
        self.plot_button = ttk.Button(
            self.tool_frame, text="Plot", command=self.handle_plot
        )
        self.plot_button.grid(row=0, column=0, sticky="ew", padx=2, pady=0)

        self.toggle_axis_button = ttk.Button(
            self.tool_frame, text="Toggle Axis", command=self.toggle_axis
        )
        self.toggle_axis_button.grid(row=0, column=1, sticky="ew", padx=2, pady=0)
        self.plot_button = ttk.Button(
            self.tool_frame, text="Output", command=self.handle_out
        )
        self.plot_button.grid(row=0, column=3, sticky="ew", padx=2, pady=0)

        self.output_label = tk.Label(
            self.left_frame, text="Output Filename:", fg="black"
        )
        self.output_label.grid(row=9, column=0, sticky="w", padx=2, pady=0)

        self.output_input = tk.Entry(self.left_frame)
        self.output_input.grid(row=10, column=0, sticky="ew", padx=2, pady=0)
        self.right_frame = tk.Frame(self.root, bd=2)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=1, pady=2)
        self.right_frame.grid_rowconfigure(1, weight=3)  # Messages
        self.right_frame.grid_rowconfigure(4, weight=2)  # Tree
        self.right_frame.grid_columnconfigure(0, weight=1)

        # 创建 Notebook
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=2, pady=0)
        # 创建 Messages 页
        self.messages_frame = tk.Frame(self.notebook)
        self.messages_frame.grid_rowconfigure(1, weight=1)  # Messages
        self.messages_frame.grid_columnconfigure(0, weight=1)
        self.message_box = ScrolledText(self.messages_frame, wrap=tk.WORD)
        self.message_box.grid(row=1, column=0, sticky="nsew", padx=2, pady=0)
        self.message_box.config(state="disabled")
        self.clear_button = ttk.Button(
            self.messages_frame, text="Clear", command=self.clear_messages
        )
        self.clear_button.grid(row=2, column=0, sticky="e", padx=2, pady=0)

        # 添加 Messages 页到 Notebook
        self.notebook.add(self.messages_frame, text="Messages")
        # 创建 Preview 页
        self.preview_frame = tk.Frame(self.notebook)
        self.preview_frame.grid_rowconfigure(0, weight=1)  # 图形预览
        self.preview_frame.grid_columnconfigure(0, weight=1)

        # 添加 Preview 页到 Notebook
        self.notebook.add(self.preview_frame, text="Preview")

        self.property_header_frame = tk.Frame(self.right_frame)
        self.property_header_frame.grid(row=3, column=0, sticky="ew", padx=2, pady=0)
        self.property_header_frame.grid_columnconfigure(0, weight=1)
        self.property_label = tk.Label(
            self.property_header_frame,
            text="Properties",
            fg="black",
            font=("Serif", 12, "bold"),
        )
        self.property_label.grid(row=0, column=0, sticky="w", padx=0, pady=0)
        self.export_template_button = ttk.Button(
            self.property_header_frame,
            text="Export Template",
            command=self.export_template,
        )
        self.export_template_button.grid(row=0, column=1, sticky="e", padx=0, pady=0)

        self.property_tree = ttk.Treeview(
            self.right_frame, columns=("Value",), show="tree headings"
        )
        self.property_tree.heading("#0", text="Property Name")
        self.property_tree.heading("Value", text="Value")
        self.property_tree.column("#0", stretch=False)
        self.property_tree.column("Value", stretch=True)
        self.property_tree.grid(row=4, column=0, sticky="nsew", padx=2, pady=0)

        self.populate_tree()
        self.update_palette_preview()
        self.left_frame.grid_propagate(False)
        self.right_frame.grid_propagate(False)
        self.notebook.grid_propagate(False)

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.restore_streams()

    def restore_streams(self):
        if getattr(self, "_old_stdout", None) is not None and sys.stdout is getattr(
            self, "_stdout_redirector", None
        ):
            sys.stdout = self._old_stdout
        if getattr(self, "_old_stderr", None) is not None and sys.stderr is getattr(
            self, "_stderr_redirector", None
        ):
            sys.stderr = self._old_stderr

    def close(self):
        self.restore_streams()
        self.root.destroy()

    def flush_pending_logs(self):
        for message in self._pending_log_messages:
            self.log_message(message)
        self._pending_log_messages.clear()

    def populate_tree(self):
        def expand_all(tree, parent=""):
            """递归展开 Treeview 中的所有节点。

            Args:
                tree: ttk.Treeview 对象。
                parent: 当前节点的父节点 ID（递归时使用）。
            """
            # 获取当前父节点的所有子节点
            children = tree.get_children(parent)
            for child in children:
                tree.item(child, open=True)  # 展开当前节点
                expand_all(tree, child)  # 递归展开子节点

        """根据 HyperPlot 的属性填充 Treeview"""
        self.property_tree.delete(*self.property_tree.get_children())
        self.insert_tree_items(
            "",
            {"root": self.plotter.get_plot_preferences(*self.plotter_properties)},
        )
        expand_all(self.property_tree)

    @staticmethod
    def palette_text_color(color):
        color = str(color).strip()
        if color.lower() == "black":
            return "white"
        if color.lower() == "white":
            return "black"
        if color.startswith("#") and len(color) == 7:
            try:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
            except ValueError:
                return "black"
            brightness = (0.299 * r + 0.587 * g + 0.114 * b)
            return "black" if brightness > 150 else "white"
        return "black"

    def update_palette_preview(self):
        """刷新 Batch Style 短颜色码预览。"""
        if not hasattr(self, "palette_frame"):
            return

        for widget in self.palette_frame.winfo_children():
            widget.destroy()

        palette = self.plotter.resolved_color_palette()
        for column, key in enumerate(HyperPlot.SHORT_COLOR_CODES):
            color = palette.get(key, key)
            try:
                swatch = tk.Label(
                    self.palette_frame,
                    text=key,
                    bg=color,
                    fg=self.palette_text_color(color),
                    width=4,
                    relief="solid",
                    borderwidth=1,
                )
            except tk.TclError:
                swatch = tk.Label(
                    self.palette_frame,
                    text=f"{key}:?",
                    width=4,
                    relief="solid",
                    borderwidth=1,
                )
            swatch.grid(row=0, column=column, sticky="ew", padx=1, pady=1)
            self.palette_frame.grid_columnconfigure(column, weight=1)

    def insert_tree_items(self, parent, data):
        """递归地将数据插入 Treeview 中"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    node_id = self.property_tree.insert(
                        parent, "end", text=key, values=("",)
                    )
                    self.insert_tree_items(node_id, value)
                else:
                    self.property_tree.insert(parent, "end", text=key, values=(value,))
        elif isinstance(data, list):
            for index, item in enumerate(data):
                if isinstance(item, dict):
                    node_id = self.property_tree.insert(
                        parent, "end", text=f"[{index}]", values=("",)
                    )
                    self.insert_tree_items(node_id, item)
                else:
                    self.property_tree.insert(
                        parent, "end", text=f"[{index}]", values=(item,)
                    )
        else:
            self.property_tree.insert(parent, "end", text="", values=(data,))

    def init_context_menus(self):
        """初始化右键菜单"""
        # Workbench 右键菜单
        self.common_menu = Menu(self.root, tearoff=0)
        self.common_menu.add_command(
            label="Edit Curve...", command=self.edit_selected_curve
        )
        self.common_menu.add_separator()
        self.common_menu.add_command(
            label="Delete Selected", command=self.delete_selected_elements
        )
        self.common_menu.add_command(
            label="Set as Background", command=self.set_selected_as_background
        )
        self.common_menu.add_command(
            label="Unset Background", command=self.unset_selected_background
        )

        # 为 Listbox 绑定右键菜单
        self.selection_list.bind("<Button-3>", self.show_workbench_menu)

        # Treeview 右键菜单
        self.tree_menu = Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Edit Property", command=self.edit_property)
        self.tree_menu.add_command(
            label="Insert Property", command=self.insert_property
        )
        self.tree_menu.add_command(
            label="Delete Property", command=self.delete_property
        )

        # 为 Treeview 绑定右键菜单
        self.property_tree.bind(
            "<Button-3>", lambda event: self.show_menu(self.tree_menu, event)
        )

    @preserve_listbox_selection
    def edit_property(self):
        """编辑 Treeview 的属性"""
        selected_item = self.property_tree.selection()
        if selected_item:
            item = selected_item[0]
            current_value = self.property_tree.item(item, "values")[0]

            new_value = simpledialog.askstring(
                "Edit Property", "Edit property value:", initialvalue=current_value
            )

            if new_value is not None:
                self.property_tree.item(item, values=(new_value,))
                self.update_plotter_property()

    @preserve_listbox_selection
    def insert_property(self):
        """插入新的属性"""
        selected_item = self.property_tree.selection()
        if selected_item:
            parent = selected_item[0]
        else:
            parent = ""

        property_name = simpledialog.askstring(
            "Insert Property", "Enter property name:"
        )
        property_value = simpledialog.askstring(
            "Insert Property", "Enter property value:"
        )

        if property_name and property_value:
            self.property_tree.insert(
                parent, "end", text=property_name, values=(property_value,)
            )
            self.update_plotter_property()

    @preserve_listbox_selection
    def delete_property(self):
        """删除选中的属性"""
        selected_item = self.property_tree.selection()
        if selected_item:
            for item in selected_item:
                self.property_tree.delete(item)
                self.update_plotter_property()

    def update_plotter_property(self):
        """更新 HyperPlot 的属性"""
        try:
            self.plotter.set_plot_preferences(
                **treeview_to_dict(self.property_tree)["root"]
            )
        except ValueError as e:
            self.log_message(f"Invalid property: {str(e)}")
            messagebox.showerror("Invalid Property", str(e))
            self.populate_tree()
            self.update_palette_preview()
            return
        self.populate_tree()
        self.update_palette_preview()

    def selected_element_indices(self):
        return list(self.selection_list.curselection())

    def toggle_select_all(self):
        item_count = self.selection_list.size()
        if item_count == 0:
            return

        selected_count = len(self.selection_list.curselection())
        if selected_count == item_count:
            self.selection_list.selection_clear(0, tk.END)
            self.log_message("Cleared Workbench selection.")
        else:
            self.selection_list.selection_set(0, tk.END)
            self.log_message(f"Selected all {item_count} Workbench element(s).")

    def invert_selection(self):
        item_count = self.selection_list.size()
        if item_count == 0:
            return

        selected = set(self.selection_list.curselection())
        self.selection_list.selection_clear(0, tk.END)
        for index in range(item_count):
            if index not in selected:
                self.selection_list.selection_set(index)
        self.log_message("Inverted Workbench selection.")

    def edit_selected_curve(self):
        selected_indices = self.selected_element_indices()
        if not selected_indices:
            self.log_message("No element selected for editing.")
            return

        index = selected_indices[0]
        detail = self.plotter.element_detail(index)
        dialog = Toplevel(self.root)
        dialog.title("Edit Curve")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.grid_columnconfigure(1, weight=1)

        tk.Label(dialog, text="Legend").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        legend_var = tk.StringVar(value=detail["label"])
        legend_input = ttk.Entry(dialog, textvariable=legend_var, width=32)
        legend_input.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        tk.Label(dialog, text="Style").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        style_var = tk.StringVar(value=detail["ls"])
        style_input = ttk.Entry(dialog, textvariable=style_var, width=32)
        style_input.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        tk.Label(dialog, text="Axis").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        axis_var = tk.StringVar(value=detail["axis"])
        axis_input = ttk.Combobox(
            dialog,
            textvariable=axis_var,
            values=("left", "right"),
            state="readonly",
            width=12,
        )
        axis_input.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        button_frame = tk.Frame(dialog)
        button_frame.grid(row=3, column=0, columnspan=2, sticky="e", padx=8, pady=8)

        def apply_changes():
            updated_count = self.plotter.update_element_style(
                index,
                label=legend_var.get().strip(),
                ls=style_var.get().strip() or "-",
                axis=axis_var.get(),
            )
            self.update_selection_list()
            self.selection_list.selection_set(index)
            dialog.destroy()
            target = "background group" if detail["is_background"] else "curve"
            self.log_message(f"Updated {target} style ({updated_count} element(s)).")

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).grid(
            row=0, column=0, padx=2
        )
        ttk.Button(button_frame, text="Apply", command=apply_changes).grid(
            row=0, column=1, padx=2
        )

        legend_input.focus_set()
        dialog.bind("<Return>", lambda _: apply_changes())
        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def delete_selected_elements(self):
        selected_indices = self.selected_element_indices()
        if not selected_indices:
            self.log_message("No elements selected for deletion.")
            return

        deleted_count = self.plotter.delete_elements(selected_indices)
        self.update_selection_list()
        self.log_message(f"Deleted {deleted_count} selected element(s).")

    def set_selected_as_background(self):
        selected_indices = self.selected_element_indices()
        if not selected_indices:
            self.log_message("No elements selected for background.")
            return

        updated_count = self.plotter.set_background(selected_indices)
        self.update_selection_list()
        self.log_message(f"Set {updated_count} selected element(s) as background.")

    def unset_selected_background(self):
        selected_indices = self.selected_element_indices()
        if not selected_indices:
            self.log_message("No elements selected for background reset.")
            return

        updated_count = self.plotter.unset_background(selected_indices)
        self.update_selection_list()
        self.log_message(f"Unset background for {updated_count} selected element(s).")

    def export_template(self):
        """导出当前绘图属性为模板。"""
        try:
            self.update_plotter_property()
            template_path = self.plotter.save_template()
            self.log_message(f"Template exported: {template_path}")
        except Exception as e:
            self.log_message(f"Template export failed: {str(e)}")

    def show_menu(self, menu: Menu, event: tk.Event):
        """显示指定的右键菜单，并关闭其他菜单"""
        self.close_all_menus()
        menu.post(event.x_root, event.y_root)
        return "break"

    def show_workbench_menu(self, event: tk.Event):
        if self.selection_list.size():
            index = self.selection_list.nearest(event.y)
            if index not in self.selection_list.curselection():
                self.selection_list.selection_clear(0, tk.END)
                self.selection_list.selection_set(index)
        return self.show_menu(self.common_menu, event)

    def close_all_menus(self):
        """关闭所有右键菜单"""
        self.common_menu.unpost()
        self.tree_menu.unpost()

    def get_current_plot(self):
        """处理绘图逻辑"""
        selected_indices = self.selection_list.curselection()
        if not selected_indices:
            self.log_message("No elements selected for plotting.")

        legends = self.legends_input.get()
        fig = self.plotter.get_plot(selected_indices, legends)
        return fig

    def handle_plot(self):
        self.update_plot_view(self.get_current_plot(), self.preview_frame)
        # self.display_plot_in_new_window(fig)
        self.log_message(
            f"Plotting elements with indices: {self.selection_list.curselection()}"
        )
        self.notebook.select(self.preview_frame)
        self.update_selection_list()

    def handle_out(self):
        selected_indices = self.selection_list.curselection()
        legends = self.legends_input.get()
        if not selected_indices:
            self.log_message("No elements selected for plotting.")

        fig, selected_elements = self.plotter.get_plot_with_elements(
            selected_indices, legends
        )
        self.update_plot_view(fig, self.preview_frame)
        self.display_plot_in_new_window(fig)
        output_name = self.output_input.get() or None  # 从输入框获取输出文件名

        # 调用 HyperPlot 的 out() 函数绘制选定的元素
        self.plotter.save_plot(fig, selected_elements, output_name)
        self.notebook.select(self.preview_frame)
        self.update_selection_list()

    def toggle_axis(self):
        """处理轴切换逻辑"""
        selected_indices = self.selection_list.curselection()
        if not selected_indices:
            self.log_message("No elements selected for axis toggle.")
        else:
            for label, axis_label in self.plotter.toggle_axis(selected_indices):
                self.log_message(
                    f"Toggled axis for element {label} to {axis_label}."
                )
            self.update_selection_list()  # 更新界面上的元素列表，显示新设置的轴

    def clear_messages(self):
        """清空消息区域"""
        self.message_box.config(state="normal")
        self.message_box.delete("1.0", tk.END)
        self.message_box.config(state="disabled")

    def log_message(self, message):
        """记录消息到消息区域"""
        if not hasattr(self, "message_box"):
            self._pending_log_messages.append(message)
            return
        self.message_box.config(state="normal")
        self.message_box.insert("end", message)
        self.message_box.insert("end", "\n")
        self.message_box.see("end")
        self.message_box.config(state="disabled")

    def show_message(self, message):
        """显示消息"""
        messagebox.showinfo("Info", message)

    def on_file_drop(self, event):
        """处理文件拖拽事件"""
        file_paths = self.parse_dropped_files(event.data)

        # 调用类似 `Textual` 的处理逻辑
        self.process_files(file_paths)

    def is_supported_drop_path(self, file_path):
        return file_path.lower().endswith((".csv", ".svg", ".png")) or (
            os.path.isfile(file_path) and HyperPlot.HyperPlot.is_template_path(file_path)
        )

    def parse_dropped_files(self, dropped_data):
        """解析拖拽文件的路径"""
        file_paths = self.root.tk.splitlist(dropped_data)
        file_paths = [path for path in file_paths if self.is_supported_drop_path(path)]
        return file_paths

    def process_files(self, file_paths):
        """处理文件路径的核心逻辑"""
        if not file_paths:
            self.log_message("No valid CSV, SVG, PNG, or template files were dropped.")
            return

        try:
            csv_paths = [
                file_path
                for file_path in file_paths
                if file_path.lower().endswith(".csv")
            ]
            svg_paths = [
                file_path
                for file_path in file_paths
                if file_path.lower().endswith(".svg")
            ]
            png_paths = [
                file_path
                for file_path in file_paths
                if file_path.lower().endswith(".png")
            ]
            template_paths = [
                file_path
                for file_path in file_paths
                if HyperPlot.HyperPlot.is_template_path(file_path)
            ]

            for file_path in template_paths:
                try:
                    self.plotter.load_template(file_path)
                    self.log_message(f"Template loaded: {file_path}")
                except ValueError as e:
                    self.log_message(f"Template import skipped: {str(e)}")

            for file_path in svg_paths:
                try:
                    restored_count = self.plotter.catch_svg(file_path)
                    self.set_output_filename_from_import(file_path)
                    self.log_message(
                        f"SVG state loaded from {file_path}: {restored_count} element(s)."
                    )
                except ValueError as e:
                    self.log_message(f"SVG import skipped: {str(e)}")

            for file_path in png_paths:
                try:
                    restored_count = self.plotter.catch_png(file_path)
                    self.set_output_filename_from_import(file_path)
                    self.log_message(
                        f"PNG state loaded from {file_path}: {restored_count} element(s)."
                    )
                except ValueError as e:
                    self.log_message(f"PNG import skipped: {str(e)}")

            if csv_paths and self.fastcsv_var.get():
                # FastCSV 模式激活时快速处理文件
                for file_path in csv_paths:
                    self.plotter.fastCSV(file_path, self.legends_input.get())
                    self.log_message(f"FastCSV applied to {file_path}")
            elif csv_paths:
                # 否则使用标准方法捕获文件路径
                self.plotter.catch(csv_paths)
                self.log_message(f"File(s) caught: {', '.join(csv_paths)}")

            # 文件处理完成后更新 Listbox
            self.populate_tree()
            self.update_palette_preview()
            self.update_selection_list()
            self.log_message("File processing completed.")
        except FileNotFoundError as e:
            self.log_message(f"File not found: {e.filename}")
        except Exception as e:
            if e.__class__.__name__ == "EmptyDataError":
                self.log_message(
                    f"Error: {getattr(e, 'filename', '')} is an empty file."
                )
            elif e.__class__.__name__ == "ParserError":
                self.log_message(
                    f"Error: {getattr(e, 'filename', '')} is not a valid CSV file."
                )
            else:
                self.log_message(f"An error occurred while processing files: {str(e)}")

    def set_output_filename_from_import(self, file_path):
        """用导入的可恢复图像文件名填充输出文件名。"""
        self.output_input.delete(0, tk.END)
        self.output_input.insert(0, os.path.basename(file_path))

    def update_selection_list(self):
        """将 plotter 的元素更新到 Listbox 中"""
        selected_indices = self.selection_list.curselection()
        self.selection_list.delete(0, tk.END)  # 清除当前列表内容
        for row in self.plotter.element_rows():
            # 根据元素属性添加到 Listbox
            axis_info = "(Right Axis)" if row["axis"] == "right" else "(Left Axis)"
            background_info = " | [BG]" if row["is_background"] else ""
            self.selection_list.insert(
                tk.END,
                f"{row['file_name']} | {row['x_label']} | {row['label']} | {row['ls']}{background_info} | {axis_info}",
            )
        for index in selected_indices:
            self.selection_list.selection_set(index)

    def display_plot_in_new_window(self, fig):
        # 创建新的 Tkinter 窗口
        new_window = Toplevel(self.root)
        new_window.title("Plotview")

        # 将图形嵌入到新窗口中
        self.generate_plot_view(fig, new_window, expand=True)
        # 提示用户操作成功
        self.log_message("Plot displayed in a new window.")

    def generate_plot_view(self, fig, master, expand=False):

        canvas = FigureCanvasTkAgg(fig, master=master)
        canvas.draw()
        canvas.get_tk_widget().pack(
            expand=expand, fill="both" if expand else None
        )  # 自动调整大小

    def update_plot_view(self, fig, master):
        """更新已有窗口中的绘图视图"""
        # 清除旧画布
        for widget in master.winfo_children():
            widget.destroy()
        # 创建新的画布并重新绘制
        self.generate_plot_view(fig, master)


if __name__ == "__main__":
    app = PlotApp()
    app.run()
