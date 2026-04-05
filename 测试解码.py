import base64
from urllib.parse import unquote

p = '2085e1bb7f92ee46b73624944530228c53739dc1baa59ff5043b91dd332dcf97JmltdHM9MTc2OTA0MDAwMA'
print('p value:', p)
enc = unquote(p)
print('after unquote:', enc)

# 尝试 Base64 解码
missing_padding = len(enc) % 4
if missing_padding != 0:
    enc += '=' * (4 - missing_padding)

try:
    decoded = base64.urlsafe_b64decode(enc)
    result = decoded.decode('utf-8', errors='ignore')
    print('decoded as string:', result)
    print('starts with http?', result.startswith('http'))
except Exception as e:
    print('decode error:', e)

