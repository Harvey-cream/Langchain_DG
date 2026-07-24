from gmssl import SM2

# 创建 SM2 对象
sm2 = SM2()

# 生成密钥对
private_key = sm2.generate_private_key()
public_key = sm2.generate_public_key(private_key)

print("私钥 (privateKey):")
print(private_key.hex())
print("\n公钥 (publicKey):")
print(public_key.hex())