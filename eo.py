import os
import re
import time
import subprocess
import ipaddress
import socket
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Optional

# ===================== 配置区域 =====================
INPUT_FILE = "/修改为你的文件目录绝对路径/ip.txt"
OUTPUT_FILE = "/修改为你的文件目录绝对路径/best_ip.txt"
TEST_TARGET = "114.114.114.114"  # 测试目标（域名或IP）114.114.114.114 8.8.8.8 1.1.1.1 www.google.com
PING_COUNT = 3                 # 每个IP的ping次数
TIMEOUT = 2                    # 单次ping超时时间（秒）
PORT_TIMEOUT = 2               # 端口检测超时时间（秒）
MAX_WORKERS = 50               # 最大并发线程数
MIN_SCORE = 80                 # 最低合格分数
TOP_DISPLAY = 5                # 终端显示的最优IP数量
TOP_SAVE = 10                  # 文件保存的最优IP数量
# ====================================================

class IPOptimizer:
    def __init__(self):
        self.ips = self._load_ips()
        self.results = []  # 存储结果：(ip, 平均延迟, 丢包率, 443端口状态, 分数)

    def _load_ips(self) -> List[str]:
        """加载并解析IP/CIDR列表（去重）"""
        ips = []
        input_path = Path(INPUT_FILE)
        
        if not input_path.exists():
            print(f"错误：输入文件 {INPUT_FILE} 不存在")
            exit(1)
        
        with open(input_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        
        for line in lines:
            # 解析CIDR（如192.168.1.0/24）
            if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", line):
                try:
                    network = ipaddress.ip_network(line, strict=False)
                    ips.extend([str(ip) for ip in network.hosts()])
                except ValueError:
                    print(f"警告：无效CIDR {line}，已跳过")
            # 解析单个IP
            elif re.match(r"^\d+\.\d+\.\d+\.\d+$", line):
                ips.append(line)
            else:
                print(f"警告：无效IP {line}，已跳过")
        
        unique_ips = list(set(ips))
        print(f"成功加载 {len(unique_ips)} 个有效IP（已去重）")
        return unique_ips

    def _ping_ip(self, ip: str) -> Tuple[Optional[float], Optional[float]]:
        """测试单个IP的延迟和丢包率（适配Debian系统）"""
        cmd = [
            "ping",
            "-c", str(PING_COUNT),    # 发送3个包
            "-W", str(TIMEOUT),       # 每个包超时2秒
            TEST_TARGET               # 目标地址（放在最后，Debian要求）
        ]
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=TIMEOUT * PING_COUNT + 2  # 总超时时间
            )
            output = result.stdout + result.stderr  # 合并输出
            
            # 解析丢包率
            loss_match = re.search(r"(\d+)% packet loss", output)
            if not loss_match:
                return (None, None)
            loss_rate = int(loss_match.group(1))
            
            # 解析延迟
            time_matches = re.findall(r"time=(\d+\.?\d*) ms", output)
            if not time_matches:
                return (None, loss_rate)
            
            avg_delay = sum(float(t) for t in time_matches) / len(time_matches)
            return (avg_delay, loss_rate)
        
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"IP {ip} ping测试异常：{str(e)}")
            return (None, 100)

    def _check_port_443(self, ip: str) -> bool:
        """检测IP的443端口是否可连通"""
        try:
            # 创建TCP连接，检测443端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(PORT_TIMEOUT)  # 超时时间
                result = s.connect_ex((ip, 443))  # 0表示成功，非0表示失败
                return result == 0
        except Exception as e:
            print(f"IP {ip} 443端口检测异常：{str(e)}")
            return False

    def _calculate_score(self, avg_delay: float, loss_rate: float, port_443_ok: bool) -> int:
        """计算IP评分（100分为满分，增加443端口权重）"""
        if loss_rate == 100 or not port_443_ok:
            return 0  # 丢包100%或443端口不通直接判0分
        
        # 延迟得分（40分基础，延迟越低得分越高）
        delay_score = max(0, 40 - (avg_delay / 5))  # 每5ms扣1分，最低0分
        # 丢包率得分（40分基础，丢包率越低得分越高）
        loss_score = 40 * (1 - loss_rate / 100)
        # 443端口得分（固定20分，确保端口通畅是基础）
        port_score = 20
        
        return int(min(100, delay_score + loss_score + port_score))

    def optimize(self):
        """批量检测并筛选最优IP"""
        if not self.ips:
            print("无有效IP可检测，程序退出")
            return
        
        print(f"\n开始检测（并发数：{MAX_WORKERS}，目标：{TEST_TARGET}，含443端口检测）...")
        start_time = time.time()
        
        # 多线程并发检测（同时进行ping和443端口检测）
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务：先ping，再检测端口
            futures = {}
            for ip in self.ips:
                # 先执行ping测试，再执行端口检测
                ping_future = executor.submit(self._ping_ip, ip)
                port_future = executor.submit(self._check_port_443, ip)
                futures[(ping_future, port_future)] = ip
            
            for (ping_future, port_future), ip in futures.items():
                try:
                    # 获取ping结果
                    avg_delay, loss_rate = ping_future.result()
                    if avg_delay is None or loss_rate is None:
                        print(f"❌ {ip}：ping检测失败")
                        continue
                    
                    # 获取443端口检测结果
                    port_443_ok = port_future.result()
                    
                    # 计算分数并记录
                    score = self._calculate_score(avg_delay, loss_rate, port_443_ok)
                    self.results.append((ip, avg_delay, loss_rate, port_443_ok, score))
                    
                    # 输出实时结果
                    status = "✅" if score >= MIN_SCORE else "⚠️"
                    port_status = "通畅" if port_443_ok else "不通"
                    print(
                        f"{status} {ip}：平均延迟 {avg_delay:.2f}ms，丢包率 {loss_rate}%，"
                        f"443端口：{port_status}，得分 {score}（{'合格' if score >= MIN_SCORE else '不合格'}）"
                    )
                except Exception as e:
                    print(f"❌ {ip}：处理错误 - {str(e)}")

        # 筛选合格IP并排序（按分数降序，同分数按延迟升序）
        qualified_ips = [res for res in self.results if res[4] >= MIN_SCORE]
        qualified_ips.sort(key=lambda x: (-x[4], x[1]))  # 核心排序逻辑

        # 保存前TOP_SAVE个最优IP
        save_ips = qualified_ips[:TOP_SAVE]
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for res in save_ips:
                f.write(f"{res[0]}\n")  # 仅保存IP地址

        # 输出总结
        total_time = time.time() - start_time
        print(f"\n检测完成（耗时 {total_time:.2f} 秒）")
        print(f"合格IP总数：{len(qualified_ips)}（最低分 {MIN_SCORE}，需443端口通畅）")
        print(f"已保存前 {len(save_ips)} 个最优IP到 {OUTPUT_FILE}")
        
        # 显示Top TOP_DISPLAY最优IP
        display_ips = qualified_ips[:TOP_DISPLAY]
        if display_ips:
            print(f"\nTop {len(display_ips)} 最优IP：")
            for i, res in enumerate(display_ips, 1):
                print(
                    f"{i}. {res[0]}（得分：{res[4]}，延迟：{res[1]:.2f}ms，"
                    f"丢包率：{res[2]}%，443端口：{'通畅' if res[3] else '不通'}）"
                )

if __name__ == "__main__":
    optimizer = IPOptimizer()
    optimizer.optimize()