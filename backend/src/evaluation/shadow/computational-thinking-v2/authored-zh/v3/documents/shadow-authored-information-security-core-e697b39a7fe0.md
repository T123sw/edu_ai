# 机密性、完整性与身份认证｜核心讲义

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 准确区分机密性、完整性与身份认证的定义及安全目标。
2. 理解加密算法、哈希函数与消息认证码在实现上述目标中的作用。
3. 能够识别常见安全架构中的逻辑漏洞，特别是加密与认证的混淆。

## 准确概念与边界
在信息安全领域，机密性、完整性与身份认证是构建可信系统的三大支柱，三者缺一不可，但技术实现路径不同。

**机密性（Confidentiality）**：确保信息仅被授权实体访问。其核心边界在于“防窃取”。若数据被未授权方获取且可 read，则机密性丧失。主要技术手段为加密（Encryption），包括对称加密（如 AES）与非对称加密（如 RSA）。

**完整性（Integrity）**：确保信息在存储或传输过程中未被未授权篡改、插入或删除。其核心边界在于“防篡改”。即使数据未泄露，若被恶意修改（如转账金额由 100 改为 1000），完整性即丧失。主要技术手段为哈希函数（Hash）与消息认证码（MAC）。

**身份认证（Authentication）**：确认通信实体声称的身份是真实的。其核心边界在于“防伪装”。主要技术手段为数字签名、口令认证或数字证书。

需注意，加密并不天然保证完整性。例如，流加密模式下，攻击者翻转密文比特位，解密后的明文对应位也会翻转，而接收方无法察觉。因此，必须显式引入完整性校验机制。

## 机制与步骤
实现三者兼顾的典型流程如下：
1. **密钥协商**：通信双方通过安全渠道共享对称密钥 $K$ 或交换公钥。
2. **完整性保护**：发送方计算消息 $M$ 的认证标签 $T = \text{MAC}(K, M)$ 或签名 $S = \text{Sign}(PrivateKey, M)$。
3. **机密性保护**：将消息与标签拼接 $P = M || T$，进行加密 $C = \text{Encrypt}(K, P)$。
4. **传输**：发送密文 $C$。
5. **验证与解密**：接收方解密 $P = \text{Decrypt}(K, C)$，分离 $M$ 与 $T$，重新计算 $T' = \text{MAC}(K, M)$ 并比对 $T == T'$。

## 完整例子与代码
假设 Alice 向 Bob 发送敏感指令 "TRANSFER 100"。使用 HMAC-SHA256 保证完整性与认证，AES 保证机密性。

```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import hashlib
import hmac
import os

def secure_send(message, key):
    # 1. 完整性与认证 (HMAC)
    # 使用 key 的派生值作为 HMAC 密钥，避免密钥复用风险
    mac_key = hashlib.sha256(key + b'mac').digest()
    tag = hmac.new(mac_key, message, hashlib.sha256).digest()
    payload = message + tag
    
    # 2. 机密性 (AES-GCM 模式同时提供加密与完整性，此处演示分离概念用 CBC+HMAC)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    # 简单填充处理
    padding_len = 16 - (len(payload) % 16)
    payload += bytes([padding_len] * padding_len)
    
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(payload) + encryptor.finalize()
    return iv, ciphertext

# 模拟密钥
key = os.urandom(32) 
msg = b"TRANSFER 100"
iv, ct = secure_send(msg, key)
print(f"密文长度：{len(ct)} 字节")
```

## 复杂度与权衡
安全机制引入计算开销与延迟。
1. **计算复杂度**：哈希函数通常为 $O(n)$，加密算法如 AES 为 $O(n)$，但非对称加密（RSA）为 $O(k^3)$（$k$为密钥长度）。因此在大数据量传输中，通常采用“数字信封”技术：用对称加密传数据，非对称加密传密钥。
2. **空间开销**：完整性标签（如 SHA-256 输出 32 字节）和初始化向量（IV）会增加传输包的大小。
3. **安全性权衡**：密钥长度越长越安全，但加解密越慢。需根据数据价值选择合适参数（如 AES-128  vs  AES-256）。

## 常见误区
1. **误区一**：“只要加密了，数据就不会被篡改。”
   **纠正**：某些加密模式（如 ECB、CBC）不具备完整性校验功能，密文被修改后仍能解密出有意义的乱码，必须配合 MAC 或使用 AEAD 模式（如 GCM）。
2. **误区二**：“哈希值可以还原原始数据。”
   **纠正**：哈希是单向函数，不可逆。它用于校验而非保密。
3. **误区三**：“身份认证只需要密码。”
   **纠正**：静态密码易被重放或窃取，现代认证需结合动态令牌或数字签名。

## 自测题与答案
1. **问**：若攻击者仅能窃听但不能修改数据，主要破坏了哪个属性？
   **答**：机密性。
2. **问**：HMAC 算法中，若密钥泄露，攻击者能否伪造合法消息？
   **答**：能。HMAC 的安全性依赖于密钥的保密性。
3. **问**：为什么不建议直接使用 `Hash(Message)` 作为完整性校验？
   **答**：因为攻击者可以篡改 Message 后重新计算 Hash 并替换原 Hash 值。必须使用带密钥的 MAC 或数字签名。
