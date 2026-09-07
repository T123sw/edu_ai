# Edu-AI 启动与访问

## 一、在服务器上启动项目

进入项目和 Conda 环境：

```bash
cd /home/zxqs_ep/Edu_AI
source /home/zxqs_ep/miniforge3/etc/profile.d/conda.sh
conda activate edu-ai
```

查看服务是否已经运行：

```bash
systemctl is-active postgresql edu-ai-openmaic edu-ai-backend nginx
```

如果四行都显示 `active`，项目已经启动，无需重复操作。

如果服务没有运行，执行：

```bash
bash scripts/start-production.sh
```

按提示输入服务器的 `sudo` 密码。脚本显示以下内容即启动成功：

```text
Edu-AI is ready: http://127.0.0.1/
```

退出 VS Code、SSH 或 Conda 不会停止已经启动的服务。

## 二、在自己的电脑上访问前端

打开自己电脑的 PowerShell、Windows Terminal、Terminal 或其他本地终端。不要在服务器终端或 VS Code 远程终端中执行下面的命令。

SSH 使用默认端口 `22` 时：

```bash
ssh -N -L 8080:127.0.0.1:80 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 zxqs_ep@222.27.241.65
```

SSH 使用自定义端口时：

```bash
ssh -N -p <SSH端口> -L 8080:127.0.0.1:80 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 zxqs_ep@222.27.241.65
```

服务器地址已经填写为 `222.27.241.65`。只有 SSH 不使用默认端口 `22` 时，才需要使用第二条命令并替换 `<SSH端口>`。完成密码或密钥认证后，保持这个终端窗口运行。

然后在自己电脑的浏览器中打开：

```text
http://127.0.0.1:8080/
```

如果提示 `Address already in use`，说明电脑本地的 `8080` 已被占用。可改用 `18080`：

```bash
ssh -N -L 18080:127.0.0.1:80 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 zxqs_ep@222.27.241.65
```

浏览器地址也要改为：

```text
http://127.0.0.1:18080/
```

关闭 SSH 映射终端或按 `Ctrl+C` 后，浏览器将无法继续访问，但服务器上的项目仍会运行。
