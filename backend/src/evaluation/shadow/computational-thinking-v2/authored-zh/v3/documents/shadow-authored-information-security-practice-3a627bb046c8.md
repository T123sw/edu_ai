# 机密性、完整性与身份认证｜案例与实践

> 编写：Edu AI 计算思维课程知识库  
> 类型：原创教学资料  
> 语言：简体中文  
> 许可：CC BY-NC-SA 4.0  
> 编写依据：课程图谱 v2 与所列课程标准/开放教材，仅作知识体系参照

## 学习目标
1. 能够在具体业务场景中设计包含机密性、完整性与认证的安全方案。
2. 通过编程实现安全数据的封装与解封装流程。
3. 学会通过边界测试验证安全机制的有效性。

## 真实问题情境
某大学教务系统需通过公共网络接收教师提交的期末成绩。数据包含学生 ID 与分数。系统面临以下威胁：
1. 黑客窃听网络，获取学生隐私（需机密性）。
2. 黑客篡改分数，如将 60 分改为 90 分（需完整性）。
3. 黑客伪装成教师提交虚假成绩（需身份认证）。

请你设计并实现一个“安全成绩提交模块”，模拟教师端打包数据与服务器端验证数据的过程。

## 输入输出与材料
*   **输入材料**：
    *   原始成绩数据（JSON 格式）：`{"student_id": "2023001", "score": 85}`
    *   共享密钥（模拟预分发）：`b'SecretKey12345678901234567890'` (32 字节)
*   **输出要求**：
    *   教师端输出：十六进制表示的密文包。
    *   服务器端输出：验证结果（成功/失败）及解密后的原始数据。

## 分步任务
1.  **环境准备**：安装必要库 `pip install cryptography`。
2.  **构建发送函数**：
    *   生成随机 IV（初始化向量）。
    *   计算数据的 HMAC 签名（使用 SHA-256）。
    *   将“原始数据 + 签名”进行 AES 加密。
    *   返回 IV 与密文。
3.  **构建接收函数**：
    *   使用 IV 解密密文。
    *   分离原始数据与签名。
    *   重新计算 HMAC 并比对。
    *   若比对失败，抛出异常；若成功，返回 JSON 数据。
4.  **篡改测试**：手动修改密文中的一个字节，观察接收端反应。

## 参考实现
```python
import json
import hmac
import hashlib
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

KEY = b'SecretKey12345678901234567890'

def pad(data):
    bs = 16
    padding_len = bs - (len(data) % bs)
    return data + bytes([padding_len] * padding_len)

def unpad(data):
    padding_len = data[-1]
    return data[:-padding_len]

def send_grade(grade_dict, key):
    data_bytes = json.dumps(grade_dict).encode('utf-8')
    # 认证：生成 HMAC
    mac = hmac.new(key, data_bytes, hashlib.sha256).digest()
    payload = pad(data_bytes + mac)
    
    # 机密性：AES 加密
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(payload) + encryptor.finalize()
    return iv, ciphertext

def receive_grade(iv, ciphertext, key):
    try:
        # 解密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        payload = decryptor.update(ciphertext) + decryptor.finalize()
        payload = unpad(payload)
        
        # 分离数据与签名
        data_bytes, received_mac = payload[:-32], payload[-32:]
        
        # 验证完整性与认证
        expected_mac = hmac.new(key, data_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_mac, received_mac):
            return {"status": "FAIL", "reason": "Integrity Check Failed"}
            
        return {"status": "SUCCESS", "data": json.loads(data_bytes)}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)}

# 主流程测试
if __name__ == "__main__":
    original = {"student_id": "2023001", "score": 85}
    iv, ct = send_grade(original, KEY)
    print(f"发送密文片段：{ct[:16].hex()}...")
    
    result = receive_grade(iv, ct, KEY)
    print(f"正常接收：{result}")
    
    # 边界测试：篡改密文
    tampered_ct = bytearray(ct)
    tampered_ct[0] ^= 0xFF  # 翻转第一个字节
    result_tampered = receive_grade(iv, bytes(tampered_ct), KEY)
    print(f"篡改接收：{result_tampered}")
```

## 测试与边界情况
1.  **正常路径**：密钥一致，数据未变，应返回 `SUCCESS` 及原始分数。
2.  **完整性破坏**：如代码所示，翻转密文比特位。由于使用了 HMAC，解密后的数据虽然可能变化，但签名校验必失败，应返回 `Integrity Check Failed`。
3.  **认证失败**：若接收方使用错误密钥解密，虽然可能解出数据，但 HMAC 校验将不通过（因为 HMAC 密钥也错了）。
4.  **填充错误**：若密文长度不是 16 的倍数，解密库会抛出异常，需捕获处理。

## 评价量规
| 维度 | 优秀 (A) | 合格 (B) | 需改进 (C) |
| :--- | :--- | :--- | :--- |
| **功能实现** | 加密、解密、签名、验签全部正确运行 | 能加密解密，但签名逻辑有误 | 无法运行或逻辑缺失 |
| **安全理解** | 正确理解 IV 必要性，使用 `compare_digest` 防时序攻击 | 忽略 IV 随机性，直接使用 `==` 比对签名 | 未实现签名校验 |
| **异常处理** | 能捕获解密异常与校验失败，给出明确提示 | 程序遇错直接崩溃 | 无错误处理机制 |
| **代码规范** | 函数模块化，变量命名清晰，有注释 | 代码堆砌在主流程，注释少 | 代码混乱，不可读 |

## 拓展问题
1.  **重放攻击**：若攻击者截获了合法的密文包并原样重新发送给服务器，服务器会验证通过。如何防止？（提示：在数据中加入时间戳或随机 nonce，并维护已接收记录）。
2.  **密钥管理**：本例中密钥硬编码在代码中。在实际分布式系统中，如何安全地分发和存储密钥？（提示：研究 KMS 服务或 Diffie-Hellman 密钥交换）。
3.  **算法升级**：CBC 模式需手动处理填充且易受填充预言攻击。如何改用 AES-GCM 模式简化代码并提高安全性？
