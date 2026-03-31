from gmssl import sm2, sm3, func
from binascii import hexlify, unhexlify
import string
import random

# SM2密钥对
# PAIR 1: 前端请求后端 (前端用公钥加密，后端用私钥解密)
BACK_PRIVATE_KEY = "ddca2f50cf6b7980aa2bc13eb5a8edeadf47517cb8e97904f4b9d0a455539002"
BACK_PUBLIC_KEY = "04fdd007d303dadd6e27f32a6655edd4e00f0259a7a197ead640ba08eb987015ecea431c7a47b7bb27423bc0e643f6e7169177884e37ff169803ca40cb7f0bf394"

# PAIR 2: 后端响应前端 (后端用私钥加密，前端用公钥解密)
FRONT_PUBLIC_KEY = "046cc335dbe6df52d9b6bb6f4203f5f17c964f1365ca2eae7647477c0c770e1e23ee52b84d1d3e41573da3373148e0ef17bbb2f7fc29b9be2107f06d9a82bed669"
FRONT_PRIVATE_KEY = "ff3803fdaa6dbbc77f70f62d9bb1cfbc4c010c57c25fc44806d59f33b9a7f65a"

# 获取sm2对象
def get_sm2(pub_key, pri_key):
    # 去掉 04 前缀进行初始化是 gmssl 的标准做法
    if pub_key and pub_key.startswith("04"):
        pub_key = pub_key[2:]
    return sm2.CryptSM2(public_key=pub_key, private_key=pri_key, mode=1)

class SM2Utils:
    def __init__(self, public_key=None, private_key=None):
        self.public_key = public_key
        self.private_key = private_key
        self.sm2_crypt = get_sm2(public_key, private_key)

    def encrypt(self, data):
        if not self.public_key:
            raise ValueError("公钥未设置")
        enc_data = self.sm2_crypt.encrypt(data.encode('utf-8'))
        return hexlify(enc_data).decode('utf-8')

    def decrypt(self, data):
        if not self.private_key:
            raise ValueError("私钥未设置")
        
        print(f"--- 解密调试 ---")
        print(f"收到数据: {data}")
        
        try:
            # 使用SM2解密
            dec_data = self.sm2_crypt.decrypt(unhexlify(data))
            result = dec_data.decode('utf-8')
            print(f"解密出明文成功: {result}")
            return result
        except Exception as e:
            print(f"解密异常报错: {e}")
            # 如果SM2解密失败，尝试使用Base64解码作为后备
            try:
                import base64
                import urllib.parse
                result = urllib.parse.unquote(base64.b64decode(data).decode('utf-8'))
                print(f"Base64解码成功: {result}")
                return result
            except Exception as e2:
                print(f"Base64解码也失败: {e2}")
                raise e

def sm3_hash(data):
    return sm3.sm3_hash(func.bytes_to_list(data.encode('utf-8')))

def get_refer_code(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# 初始化工具实例
# 修复：必须传入对应的公钥，算法才能正常工作
request_handler = SM2Utils(public_key=BACK_PUBLIC_KEY, private_key=BACK_PRIVATE_KEY)
response_handler = SM2Utils(public_key=FRONT_PUBLIC_KEY, private_key=FRONT_PRIVATE_KEY)
