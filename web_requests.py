import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import csv
import webbrowser
import threading
from queue import Queue
import json
import re
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class WebRequester:
    def __init__(self, master):
        self.master = master
        master.title("Web批量请求器")
        master.geometry("1500x1000")
        
        # 颜色配置
        self.color_config = {
            "success": "#e6ffe6",
            "warning": "#fff3e6", 
            "error": "#ffe6e6",
            "matched": "#e6f3ff",
            "unmatched": "#ffffff"
        }
        
        # 状态变量
        self.running = False
        self.executor = None
        self.futures = []
        self.results_data = []  # 存储完整结果用于导出
        self.total_urls = 0
        self.completed_urls = 0
        
        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.master)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 顶部进度条框架
        self.create_top_progress_frame(main_frame)
        
        # 请求设置框架
        self.create_request_frame(main_frame)
        
        # 匹配器框架
        self.create_matcher_frame(main_frame)
        
        # 结果框架
        self.create_results_frame(main_frame)

    def create_top_progress_frame(self, parent):
        """创建顶部进度条框架"""
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill="x", pady=(0, 5))
        
        # 左侧标题
        title_label = ttk.Label(top_frame, text="Web批量请求器", font=("Arial", 12, "bold"))
        title_label.pack(side="left")
        
        # 右侧进度显示
        self.progress_display = ttk.Label(top_frame, text="就绪", font=("Arial", 10))
        self.progress_display.pack(side="right", padx=10)
        
        # 添加分隔线
        ttk.Separator(parent, orient='horizontal').pack(fill='x', pady=5)

    def create_request_frame(self, parent):
        """创建请求设置框架"""
        request_frame = ttk.LabelFrame(parent, text="请求设置", padding=5)
        request_frame.pack(fill="x", pady=5)
        
        # URL列表区域
        self.create_url_section(request_frame)
        
        # 请求方法和其他设置区域
        self.create_settings_section(request_frame)
        
        # 路径设置区域
        self.create_path_section(request_frame)
        
        # Headers和Body区域
        self.create_headers_body_section(request_frame)
        
        # 按钮区域
        self.create_buttons_section(request_frame)

    def create_url_section(self, parent):
        """创建URL列表区域"""
        ttk.Label(parent, text="URL列表（每行一个）:").grid(row=0, column=0, sticky="w", columnspan=8)
        
        # URL文本控件
        self.url_text = tk.Text(parent, height=5)
        self.url_text.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(0, 5))
        
        # 示例URL
        example_text = "https://httpbin.org/get\nhttps://httpbin.org/post\nhttps://httpbin.org/put\nhttps://httpbin.org/delete"
        self.url_text.insert("1.0", example_text)

    def create_settings_section(self, parent):
        """创建请求方法和其他设置区域"""
        settings_frame = ttk.Frame(parent)
        settings_frame.grid(row=2, column=0, columnspan=8, sticky="ew", pady=5)
        
        # 请求方法选择
        ttk.Label(settings_frame, text="方法:").pack(side="left")
        self.method = tk.StringVar(value="GET")
        method_combo = ttk.Combobox(settings_frame, textvariable=self.method, 
                                   values=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"], 
                                   width=10, state="readonly")
        method_combo.pack(side="left", padx=5)
        
        # 并发数设置
        ttk.Label(settings_frame, text="并发数:").pack(side="left", padx=(10, 0))
        self.concurrency = tk.IntVar(value=5)
        ttk.Spinbox(settings_frame, from_=1, to=100, textvariable=self.concurrency, 
                   width=5).pack(side="left", padx=5)
        
        # 超时设置
        ttk.Label(settings_frame, text="超时(s):").pack(side="left", padx=(10, 0))
        self.timeout = tk.DoubleVar(value=10)
        ttk.Entry(settings_frame, textvariable=self.timeout, width=5).pack(side="left", padx=5)
        
        # 请求间隔
        ttk.Label(settings_frame, text="间隔(ms):").pack(side="left", padx=(10, 0))
        self.interval = tk.IntVar(value=0)
        ttk.Entry(settings_frame, textvariable=self.interval, width=7).pack(side="left", padx=5)
        
        # 代理开关
        ttk.Label(settings_frame, text="代理:").pack(side="left", padx=(10, 0))
        self.proxy_enabled = tk.BooleanVar(value=False)
        proxy_check = ttk.Checkbutton(settings_frame, variable=self.proxy_enabled, 
                                     command=self.toggle_proxy)
        proxy_check.pack(side="left")
        
        # 代理地址输入
        self.proxy = tk.StringVar(value="http://127.0.0.1:8080")
        self.proxy_entry = ttk.Entry(settings_frame, textvariable=self.proxy, width=25, state="disabled")
        self.proxy_entry.pack(side="left", padx=5)

    def toggle_proxy(self):
        """切换代理输入框状态"""
        if self.proxy_enabled.get():
            self.proxy_entry.config(state="normal")
        else:
            self.proxy_entry.config(state="disabled")

    def create_path_section(self, parent):
        """创建URL路径设置区域"""
        path_frame = ttk.Frame(parent)
        path_frame.grid(row=3, column=0, columnspan=8, sticky="ew", pady=5)
        
        ttk.Label(path_frame, text="URL路径:").pack(side="left")
        self.url_path = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.url_path, width=50)
        path_entry.pack(side="left", padx=5)
        ttk.Label(path_frame, text="(将附加到每个URL后面)").pack(side="left")

    def create_headers_body_section(self, parent):
        """创建Headers和Body区域"""
        # Headers区域
        ttk.Label(parent, text="Headers (RAW格式):").grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.headers_text = tk.Text(parent, height=4)
        self.headers_text.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 5))
        self.headers_text.insert("1.0", "User-Agent: Mozilla/5.0\nContent-Type: application/json")
        
        # Body区域
        ttk.Label(parent, text="Body (RAW格式):").grid(row=4, column=4, sticky="w", pady=(10, 0), padx=(10, 0))
        self.body_text = tk.Text(parent, height=4)
        self.body_text.grid(row=5, column=4, columnspan=4, sticky="ew", pady=(0, 5), padx=(10, 0))

    def create_matcher_frame(self, parent):
        """创建匹配器框架"""
        matcher_frame = ttk.LabelFrame(parent, text="响应匹配器", padding=5)
        matcher_frame.pack(fill="x", pady=5)
        
        # 匹配器总开关
        self.matcher_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(matcher_frame, text="启用匹配器", 
                       variable=self.matcher_enabled).grid(row=0, column=0, sticky="w", columnspan=4)
        
        # 匹配条件框架
        conditions_frame = ttk.Frame(matcher_frame)
        conditions_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=5)
        
        # 状态码匹配 - 带开关
        self.status_match_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(conditions_frame, text="状态码匹配:", 
                       variable=self.status_match_enabled).grid(row=0, column=0, sticky="w", padx=5)
        self.status_match = tk.StringVar()
        status_entry = ttk.Entry(conditions_frame, textvariable=self.status_match, width=15, state="disabled")
        status_entry.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(conditions_frame, text="(如:200, 404, 200-299)").grid(row=0, column=2, sticky="w")
        
        # 状态码开关联动
        def toggle_status_match():
            if self.status_match_enabled.get():
                status_entry.config(state="normal")
            else:
                status_entry.config(state="disabled")
                self.status_match.set("")
        self.status_match_enabled.trace('w', lambda *args: toggle_status_match())
        
        # 响应时间匹配 - 带开关
        self.time_match_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(conditions_frame, text="响应时间匹配:", 
                       variable=self.time_match_enabled).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        time_control_frame = ttk.Frame(conditions_frame)
        time_control_frame.grid(row=1, column=1, columnspan=3, sticky="w", padx=5)
        
        self.time_match_operator = tk.StringVar(value=">")
        time_op_combo = ttk.Combobox(time_control_frame, textvariable=self.time_match_operator,
                                    values=[">", "<", ">=", "<=", "="], width=5, state="disabled")
        time_op_combo.pack(side="left")
        
        self.time_match_value = tk.DoubleVar(value=5)
        time_entry = ttk.Entry(time_control_frame, textvariable=self.time_match_value, width=10, state="disabled")
        time_entry.pack(side="left", padx=5)
        
        ttk.Label(time_control_frame, text="秒").pack(side="left")
        
        # 响应时间开关联动
        def toggle_time_match():
            if self.time_match_enabled.get():
                time_op_combo.config(state="readonly")
                time_entry.config(state="normal")
            else:
                time_op_combo.config(state="disabled")
                time_entry.config(state="disabled")
                self.time_match_value.set(0)
        self.time_match_enabled.trace('w', lambda *args: toggle_time_match())
        
        # 字符串匹配 - 带开关
        self.string_match_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(conditions_frame, text="包含字符串:", 
                       variable=self.string_match_enabled).grid(row=2, column=0, sticky="w", padx=5)
        
        string_control_frame = ttk.Frame(conditions_frame)
        string_control_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=5)
        
        self.string_match = tk.StringVar()
        string_entry = ttk.Entry(string_control_frame, textvariable=self.string_match, width=30, state="disabled")
        string_entry.pack(side="left")
        
        self.string_match_location = tk.StringVar(value="响应体")
        location_combo = ttk.Combobox(string_control_frame, textvariable=self.string_match_location,
                                     values=["响应体", "响应头", "全部"], width=10, state="disabled")
        location_combo.pack(side="left", padx=5)
        
        # 字符串匹配开关联动
        def toggle_string_match():
            if self.string_match_enabled.get():
                string_entry.config(state="normal")
                location_combo.config(state="readonly")
            else:
                string_entry.config(state="disabled")
                location_combo.config(state="disabled")
                self.string_match.set("")
        self.string_match_enabled.trace('w', lambda *args: toggle_string_match())
        
        # 正则匹配 - 带开关
        self.regex_match_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(conditions_frame, text="正则匹配:", 
                       variable=self.regex_match_enabled).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        regex_control_frame = ttk.Frame(conditions_frame)
        regex_control_frame.grid(row=3, column=1, columnspan=3, sticky="w", padx=5)
        
        self.regex_match = tk.StringVar()
        regex_entry = ttk.Entry(regex_control_frame, textvariable=self.regex_match, width=30, state="disabled")
        regex_entry.pack(side="left")
        
        self.regex_match_location = tk.StringVar(value="响应体")
        regex_loc_combo = ttk.Combobox(regex_control_frame, textvariable=self.regex_match_location,
                                      values=["响应体", "响应头", "全部"], width=10, state="disabled")
        regex_loc_combo.pack(side="left", padx=5)
        
        # 正则匹配开关联动
        def toggle_regex_match():
            if self.regex_match_enabled.get():
                regex_entry.config(state="normal")
                regex_loc_combo.config(state="readonly")
            else:
                regex_entry.config(state="disabled")
                regex_loc_combo.config(state="disabled")
                self.regex_match.set("")
        self.regex_match_enabled.trace('w', lambda *args: toggle_regex_match())
        
        # 匹配逻辑
        ttk.Label(conditions_frame, text="匹配逻辑:").grid(row=4, column=0, sticky="w", padx=5)
        self.match_logic = tk.StringVar(value="AND")
        ttk.Radiobutton(conditions_frame, text="AND (所有条件满足)", 
                       variable=self.match_logic, value="AND").grid(row=4, column=1, sticky="w")
        ttk.Radiobutton(conditions_frame, text="OR (任一条件满足)", 
                       variable=self.match_logic, value="OR").grid(row=4, column=2, sticky="w")
        
        # 测试匹配按钮
        ttk.Button(conditions_frame, text="测试匹配条件", 
                  command=self.test_matcher).grid(row=5, column=3, sticky="e", pady=5)

    def create_buttons_section(self, parent):
        """创建按钮区域"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=6, column=0, columnspan=8, sticky="ew", pady=10)
        
        self.start_btn = ttk.Button(button_frame, text="开始请求", command=self.toggle_requests, width=12)
        self.start_btn.pack(side="left", padx=2)
        
        self.export_btn = ttk.Button(button_frame, text="导出结果", command=self.export_results, width=12)
        self.export_btn.pack(side="left", padx=2)
        
        # 排序按钮
        ttk.Label(button_frame, text="排序:").pack(side="left", padx=(20, 2))
        self.sort_by = tk.StringVar(value="默认")
        sort_combo = ttk.Combobox(button_frame, textvariable=self.sort_by,
                                 values=["默认", "URL", "状态码", "响应时间", "响应大小", "匹配结果"], 
                                 width=12, state="readonly")
        sort_combo.pack(side="left", padx=2)
        sort_combo.bind('<<ComboboxSelected>>', self.sort_results)
        
        # 排序顺序
        self.sort_order = tk.StringVar(value="升序")
        ttk.Radiobutton(button_frame, text="升序", variable=self.sort_order, 
                       value="升序", command=self.sort_results).pack(side="left", padx=(10, 2))
        ttk.Radiobutton(button_frame, text="降序", variable=self.sort_order, 
                       value="降序", command=self.sort_results).pack(side="left", padx=2)
        
        # 清空按钮
        ttk.Button(button_frame, text="清空结果", command=self.clear_results, width=10).pack(side="right", padx=5)

    def create_results_frame(self, parent):
        """创建结果展示框架"""
        result_frame = ttk.LabelFrame(parent, text="请求结果（双击可跳转网页）", padding=5)
        result_frame.pack(fill="both", expand=True, pady=5)
        
        # 创建Treeview - GUI只显示关键信息
        columns = ("req_time", "url", "status", "time", "size", "matched")
        self.result_tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=20)
        
        # 设置列标题
        self.result_tree.heading("req_time", text="请求时间")
        self.result_tree.heading("url", text="URL")
        self.result_tree.heading("status", text="状态码/错误")
        self.result_tree.heading("time", text="响应时间(ms)")
        self.result_tree.heading("size", text="响应大小")
        self.result_tree.heading("matched", text="匹配结果")
        
        # 设置列宽
        self.result_tree.column("req_time", width=100, anchor="center")
        self.result_tree.column("url", width=500)
        self.result_tree.column("status", width=100, anchor="center")
        self.result_tree.column("time", width=100, anchor="center")
        self.result_tree.column("size", width=100, anchor="center")
        self.result_tree.column("matched", width=80, anchor="center")
        
        # 配置标签颜色
        for tag, color in self.color_config.items():
            self.result_tree.tag_configure(tag, background=color)
        
        # 滚动条
        scroll_y = ttk.Scrollbar(result_frame, orient="vertical", command=self.result_tree.yview)
        scroll_x = ttk.Scrollbar(result_frame, orient="horizontal", command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        # 布局
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定双击事件
        self.result_tree.bind("<Double-1>", self.open_url)

    def parse_headers(self, headers_text: str) -> Dict[str, str]:
        """解析RAW格式的Headers"""
        headers = {}
        for line in headers_text.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        return headers

    def get_proxy_dict(self) -> Dict[str, str]:
        """获取代理配置"""
        if self.proxy_enabled.get():
            proxy = self.proxy.get().strip()
            if proxy:
                return {
                    'http': proxy,
                    'https': proxy
                }
        return None

    def build_url(self, base_url: str) -> str:
        """构建完整URL（添加路径）"""
        path = self.url_path.get().strip()
        if path:
            # 确保路径格式正确
            if not path.startswith('/'):
                path = '/' + path
            if base_url.endswith('/'):
                base_url = base_url[:-1]
            return base_url + path
        return base_url

    def format_raw_request(self, method: str, url: str, headers: Dict, body: str) -> str:
        """格式化原始请求文本，可以直接复制到Burp Suite中使用"""
        lines = []
        
        # 解析URL获取路径和主机
        if url.startswith('http://'):
            url_without_proto = url[7:]
        elif url.startswith('https://'):
            url_without_proto = url[8:]
        else:
            url_without_proto = url
            
        # 分离主机和路径
        if '/' in url_without_proto:
            host = url_without_proto.split('/', 1)[0]
            path = '/' + url_without_proto.split('/', 1)[1]
        else:
            host = url_without_proto
            path = '/'
        
        # 请求行
        lines.append(f"{method} {path} HTTP/1.1")
        
        # Host头
        lines.append(f"Host: {host}")
        
        # 其他Headers
        for key, value in headers.items():
            if key.lower() != 'host':  # 避免重复Host
                lines.append(f"{key}: {value}")
        
        # 空行分隔headers和body
        lines.append("")
        
        # Body
        if body:
            lines.append(body)
        
        return "\r\n".join(lines)  # 使用CRLF换行符，符合HTTP标准

    def format_raw_response(self, status_code: int, headers: Dict, body: str) -> str:
        """格式化原始响应文本，可以直接复制到Burp Suite中使用"""
        lines = []
        
        # 状态行
        reason_phrase = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}.get(status_code, "")
        lines.append(f"HTTP/1.1 {status_code} {reason_phrase}")
        
        # Headers
        for key, value in headers.items():
            lines.append(f"{key}: {value}")
        
        # 空行分隔headers和body
        lines.append("")
        
        # Body
        if body:
            lines.append(body)
        
        return "\r\n".join(lines)  # 使用CRLF换行符，符合HTTP标准

    def check_status_match(self, status_code) -> bool:
        """检查状态码是否匹配（仅当开关开启时）"""
        if not self.status_match_enabled.get():
            return True
        
        status_pattern = self.status_match.get().strip()
        if not status_pattern:
            return False
        
        try:
            if ',' in status_pattern:
                codes = [s.strip() for s in status_pattern.split(',')]
                for code in codes:
                    if '-' in code:
                        start, end = map(int, code.split('-'))
                        if start <= status_code <= end:
                            return True
                    else:
                        if int(code) == status_code:
                            return True
                return False
            elif '-' in status_pattern:
                start, end = map(int, status_pattern.split('-'))
                return start <= status_code <= end
            else:
                return int(status_pattern) == status_code
        except:
            return False

    def check_time_match(self, response_time) -> bool:
        """检查响应时间是否匹配（仅当开关开启时）"""
        if not self.time_match_enabled.get():
            return True
        
        if not self.time_match_value.get():
            return False
        
        operator = self.time_match_operator.get()
        value = self.time_match_value.get() * 1000  # 转换为毫秒
        
        if operator == ">":
            return response_time > value
        elif operator == "<":
            return response_time < value
        elif operator == ">=":
            return response_time >= value
        elif operator == "<=":
            return response_time <= value
        elif operator == "=":
            return abs(response_time - value) < 0.001
        return False

    def check_string_match(self, response_text, response_headers) -> bool:
        """检查字符串是否匹配（仅当开关开启时）"""
        if not self.string_match_enabled.get():
            return True
        
        search_string = self.string_match.get().strip()
        if not search_string:
            return False
        
        location = self.string_match_location.get()
        
        if location == "响应体" or location == "全部":
            if search_string in response_text:
                return True
        
        if location == "响应头" or location == "全部":
            headers_str = str(response_headers)
            if search_string in headers_str:
                return True
        
        return False

    def check_regex_match(self, response_text, response_headers) -> bool:
        """检查正则表达式是否匹配（仅当开关开启时）"""
        if not self.regex_match_enabled.get():
            return True
        
        regex_pattern = self.regex_match.get().strip()
        if not regex_pattern:
            return False
        
        try:
            pattern = re.compile(regex_pattern)
            location = self.regex_match_location.get()
            
            if location == "响应体" or location == "全部":
                if pattern.search(response_text):
                    return True
            
            if location == "响应头" or location == "全部":
                headers_str = str(response_headers)
                if pattern.search(headers_str):
                    return True
            
            return False
        except re.error:
            return False

    def check_match_conditions(self, result: Dict[str, Any]) -> bool:
        """检查所有匹配条件（只检查开启的开关）"""
        if not self.matcher_enabled.get():
            return False
        
        # 收集所有开启的匹配条件的结果
        match_results = []
        
        # 状态码匹配
        if self.status_match_enabled.get():
            status_match = self.check_status_match(result['status']) if isinstance(result['status'], int) else False
            match_results.append(status_match)
        
        # 响应时间匹配
        if self.time_match_enabled.get():
            time_match = self.check_time_match(result['response_time'])
            match_results.append(time_match)
        
        # 字符串匹配
        if self.string_match_enabled.get():
            string_match = self.check_string_match(result['response_data'], result['response_headers'])
            match_results.append(string_match)
        
        # 正则匹配
        if self.regex_match_enabled.get():
            regex_match = self.check_regex_match(result['response_data'], result['response_headers'])
            match_results.append(regex_match)
        
        # 如果没有开启任何匹配条件，返回False
        if not match_results:
            return False
        
        # 根据逻辑判断
        logic = self.match_logic.get()
        
        if logic == "AND":
            return all(match_results)
        else:  # OR
            return any(match_results)

    def worker(self, url: str) -> Dict[str, Any]:
        """执行单个请求的工作线程"""
        # 记录请求发起时间
        request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取请求参数
        method = self.method.get()
        headers = self.parse_headers(self.headers_text.get("1.0", tk.END))
        body = self.body_text.get("1.0", tk.END).strip()
        
        result = {
            'request_time': request_time,
            'url': url,
            'full_url': '',
            'method': method,
            'request_headers': headers,
            'request_body': body if body else None,
            'raw_request': '',
            'status': '',
            'response_time': 0,
            'size': 0,
            'response_data': '',
            'response_headers': {},
            'raw_response': '',
            'error': None,
            'matched': False
        }
        
        try:
            # 请求间隔控制
            time.sleep(self.interval.get() / 1000)
            
            # 构建完整URL
            full_url = self.build_url(url)
            result['full_url'] = full_url
            
            # 准备请求参数
            proxies = self.get_proxy_dict()
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送请求
            response = requests.request(
                method=method,
                url=full_url,
                headers=headers,
                data=body if body else None,
                timeout=self.timeout.get(),
                proxies=proxies,
                verify=False,
                allow_redirects=True
            )
            
            # 计算响应时间
            elapsed_time = round((time.time() - start_time) * 1000, 2)
            
            # 获取响应数据
            response_text = response.text
            response_size = len(response_text.encode('utf-8'))
            
            result['status'] = response.status_code
            result['response_time'] = elapsed_time
            result['size'] = response_size
            result['response_data'] = response_text
            result['response_headers'] = dict(response.headers)
            
            # 生成原始请求和响应文本（使用CRLF）
            result['raw_request'] = self.format_raw_request(method, full_url, headers, body)
            result['raw_response'] = self.format_raw_response(
                response.status_code, 
                dict(response.headers), 
                response_text
            )
            
        except requests.exceptions.Timeout:
            result['status'] = "超时"
            result['error'] = "请求超时"
            result['raw_request'] = self.format_raw_request(method, result['full_url'] or url, headers, body)
            result['raw_response'] = "请求超时"
        except requests.exceptions.ConnectionError:
            result['status'] = "连接错误"
            result['error'] = "连接失败"
            result['raw_request'] = self.format_raw_request(method, result['full_url'] or url, headers, body)
            result['raw_response'] = "连接失败"
        except Exception as e:
            result['status'] = "错误"
            result['error'] = str(e)
            result['raw_request'] = self.format_raw_request(method, result['full_url'] or url, headers, body)
            result['raw_response'] = f"错误: {str(e)}"
        
        # 检查匹配条件
        result['matched'] = self.check_match_conditions(result)
        
        return result

    def toggle_requests(self):
        """切换开始/停止状态"""
        if self.running:
            self.stop_requests()
        else:
            self.start_requests()

    def start_requests(self):
        """开始发送请求"""
        # 获取URL列表
        urls = self.url_text.get("1.0", tk.END).strip().split('\n')
        urls = [url.strip() for url in urls if url.strip()]
        
        if not urls:
            messagebox.showwarning("警告", "请输入至少一个URL")
            return
        
        # 清空旧数据
        self.clear_results()
        self.results_data = []
        
        # 设置运行状态
        self.running = True
        self.start_btn.config(text="停止请求")
        self.export_btn.config(state="disabled")
        
        # 初始化进度
        self.total_urls = len(urls)
        self.completed_urls = 0
        self.update_progress()
        
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.concurrency.get())
        self.futures = []
        
        # 提交所有任务
        for url in urls:
            future = self.executor.submit(self.worker, url)
            self.futures.append(future)
        
        # 启动结果收集
        self.master.after(100, self.collect_results)

    def collect_results(self):
        """收集请求结果"""
        if not self.running:
            return
        
        completed = 0
        for future in self.futures[:]:
            if future.done():
                try:
                    result = future.result()
                    self.add_result_to_tree(result)
                    self.results_data.append(result)
                    self.futures.remove(future)
                    completed += 1
                except Exception as e:
                    print(f"处理结果时出错: {e}")
        
        if completed > 0:
            self.completed_urls += completed
            self.update_progress()
        
        # 继续收集或停止
        if self.futures:
            self.master.after(100, self.collect_results)
        else:
            self.stop_requests()

    def add_result_to_tree(self, result):
        """添加结果到树形视图"""
        url = result['full_url'] or result['url']
        status = result['status']
        response_time = result['response_time']
        size = result['size']
        request_time = result['request_time']
        matched = result['matched']
        
        # 根据状态码确定标签
        if isinstance(status, int):
            if 200 <= status < 300:
                tag = "success"
            elif 400 <= status < 500:
                tag = "warning"
            else:
                tag = "error"
        else:
            tag = "error"
        
        # 格式化大小显示
        size_display = self.format_size(size) if size > 0 else "0 B"
        
        # 匹配结果显示
        matched_display = "Y" if matched else "N"
        
        # 插入到树形视图
        self.result_tree.insert("", "end", 
                               values=(request_time, url, status, response_time, size_display, matched_display), 
                               tags=(tag,))
        
        # 自动滚动到底部
        self.result_tree.yview_moveto(1)

    def format_size(self, size_bytes):
        """格式化字节大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def stop_requests(self):
        """停止请求"""
        self.running = False
        self.start_btn.config(text="开始请求")
        self.export_btn.config(state="normal")
        
        if self.executor:
            self.executor.shutdown(wait=False)
        
        self.update_progress()

    def update_progress(self):
        """更新进度显示"""
        if self.total_urls > 0:
            progress_text = f"{self.completed_urls}/{self.total_urls}"
            self.progress_display.config(text=progress_text)
            
            if self.completed_urls >= self.total_urls:
                self.progress_display.config(text=f"完成 {progress_text}")
        else:
            self.progress_display.config(text="就绪")

    def clear_results(self):
        """清空结果"""
        self.result_tree.delete(*self.result_tree.get_children())
        self.results_data = []
        self.completed_urls = 0
        self.total_urls = 0
        self.progress_display.config(text="就绪")

    def sort_results(self, event=None):
        """排序结果"""
        if not self.results_data:
            return
        
        sort_by = self.sort_by.get()
        reverse = self.sort_order.get() == "降序"
        
        if sort_by == "URL":
            self.results_data.sort(key=lambda x: x['full_url'] or x['url'], reverse=reverse)
        elif sort_by == "状态码":
            self.results_data.sort(key=lambda x: str(x['status']), reverse=reverse)
        elif sort_by == "响应时间":
            self.results_data.sort(key=lambda x: x['response_time'], reverse=reverse)
        elif sort_by == "响应大小":
            self.results_data.sort(key=lambda x: x['size'], reverse=reverse)
        elif sort_by == "匹配结果":
            self.results_data.sort(key=lambda x: x['matched'], reverse=reverse)
        
        # 重新显示
        self.result_tree.delete(*self.result_tree.get_children())
        for result in self.results_data:
            self.add_result_to_tree(result)

    def test_matcher(self):
        """测试匹配器"""
        if not self.results_data:
            messagebox.showinfo("提示", "没有可测试的结果数据")
            return
        
        matched_count = 0
        for result in self.results_data:
            matched = self.check_match_conditions(result)
            if matched:
                matched_count += 1
        
        messagebox.showinfo("匹配测试结果", 
                          f"总结果数: {len(self.results_data)}\n"
                          f"匹配数量: {matched_count}\n"
                          f"匹配率: {(matched_count/len(self.results_data)*100):.1f}%")

    def export_results(self):
        """导出结果到CSV文件，原始请求和响应保持原始格式，可以直接复制到Burp Suite"""
        if not self.results_data:
            messagebox.showwarning("警告", "没有可导出的数据")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)  # 所有字段都用引号包围
                
                # 写入表头
                writer.writerow([
                    "请求时间",
                    "URL",
                    "URL+路径",
                    "状态码",
                    "响应时间(ms)",
                    "匹配结果",
                    "响应大小(bytes)",
                    "原始请求",
                    "原始响应"
                ])
                
                # 写入数据
                for result in self.results_data:
                    # 原始请求和响应保持原样，不进行任何替换
                    # CSV的QUOTE_ALL模式会确保字段内的换行符被正确处理
                    writer.writerow([
                        result['request_time'],
                        result['url'],
                        result['full_url'] or result['url'],
                        result['status'],
                        result['response_time'],
                        'Y' if result['matched'] else 'N',
                        result['size'],
                        result['raw_request'],  # 保持原始格式，包含CRLF
                        result['raw_response']   # 保持原始格式，包含CRLF
                    ])
            
            messagebox.showinfo("成功", 
                              f"结果已导出到：{file_path}\n"
                              f"原始请求和响应保持原始格式，可直接复制到Burp Suite使用！\n"
                              f"共导出 {len(self.results_data)} 条记录")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败：{str(e)}")

    def open_url(self, event):
        """双击打开URL"""
        selected = self.result_tree.selection()
        if selected:
            item = selected[0]
            # URL在第2列（索引1）
            url = self.result_tree.item(item, 'values')[1]
            if url.startswith(('http://', 'https://')):
                webbrowser.open(url)
            else:
                messagebox.showwarning("警告", "无效的URL格式")


if __name__ == "__main__":
    root = tk.Tk()
    app = WebRequester(root)
    root.mainloop()