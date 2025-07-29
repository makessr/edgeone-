# edgeone-优选
采用py形式进行优选ip服务，利用华为云国际版进行域名解析功能。
如何获取edgeone的ip列表，请访问：https://api.edgeone.ai/ips
以下是一些常见问题与解决方法：
```shell
Traceback (most recent call last):  File "/opt/1panel/apps/openresty/openresty/www/sites/updatedns.py", line 3, in <module>    from huaweicloudsdkcore.auth.credentials import BasicCredentials ModuleNotFoundError: No module named 'huaweicloudsdkcore'
```

报错 `ModuleNotFoundError: No module named 'huaweicloudsdkcore'` 说明 Python 环境中缺少华为云 SDK 的核心模块，需要安装对应的依赖包。以下是具体解决步骤：

### **解决方法：安装华为云 SDK 相关依赖**

华为云的 Python SDK 分为核心包和各服务的子包，`huaweicloudsdkcore` 是核心依赖，需先安装。

#### **1. 确认 Python 和 pip 环境**

确保使用的 `pip` 对应脚本运行的 Python 版本（避免多版本混淆）：

```shell
# 查看当前 Python 版本（需与运行脚本的版本一致）
python3 --version

# 确认 pip 对应的 Python 版本
pip3 --version  # 应显示与 Python 3.x 对应
```

#### **2. 安装核心包 `huaweicloudsdkcore`**

通过 `pip` 安装华为云 SDK 核心模块：

```shell
pip3 install huaweicloudsdkcore
```

如果脚本还涉及华为云的具体服务（如 DNS、ECS 等），还需安装对应服务的子包。例如，若脚本用于操作 DNS 服务，需额外安装：

```shell
pip3 install huaweicloudsdkdns
```

#### **3. 验证安装是否成功**

安装后，可通过以下命令检查模块是否存在：

```shell
python3 -c "import huaweicloudsdkcore; print('安装成功')"
```

如果输出 `安装成功`，则说明模块已正确安装；若仍报错，需检查 pip 安装路径是否在 Python 的搜索路径中（可通过 `echo $PYTHONPATH` 查看）。

#### **4. 特殊情况处理**

- **权限问题**：若提示 “Permission denied”，需添加 `--user` 安装到用户目录（无需管理员权限）：

```shell
pip3 install --user huaweicloudsdkcore
```



- **多 Python 版本混淆**：若系统同时存在 Python 2 和 Python 3，需明确使用 `pip3` 安装（对应 Python 3）。

安装完成后，重新运行 `updatedns.py` 脚本，即可解决模块缺失的问题。

```shell
note: If you believe this is a mistake, please contact your Python installation or OS distribution provider. You can override this, at the risk of breaking your Python installation or OS, by passing --break-system-packages.
```

### **解决方法**

#### **使用虚拟环境（最推荐，安全无风险）**

创建独立的 Python 虚拟环境，在虚拟环境中安装依赖，完全隔离系统 Python 和项目依赖。
步骤：

```shell
# 1. 安装虚拟环境工具（若未安装）
sudo apt install python3-venv  # Debian/Ubuntu 系统

# 2. 进入项目目录（例如你的脚本所在目录）
cd /opt/1panel/apps/openresty/openresty/www/sites/

# 3. 创建虚拟环境（会生成一个 venv 文件夹）
python3 -m venv venv

# 4. 激活虚拟环境
source venv/bin/activate  # 激活后终端会显示 (venv) 标识

# 5. 在虚拟环境中安装依赖（此时 pip 操作仅影响当前环境）
pip install huaweicloudsdkcore huaweicloudsdkdns  # 安装需要的包

# 6. 运行脚本（需在虚拟环境激活状态下）
python updatedns.py

# 7. 退出虚拟环境（可选）
deactivate
```