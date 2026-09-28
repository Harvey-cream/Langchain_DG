import smCrypto from 'sm-crypto';

const sm2 = smCrypto.sm2;

// SM2密钥对
// 前端使用公钥加密，后端使用私钥解密
const BACK_PUBLIC_KEY = "04fdd007d303dadd6e27f32a6655edd4e00f0259a7a197ead640ba08eb987015ecea431c7a47b7bb27423bc0e643f6e7169177884e37ff169803ca40cb7f0bf394";

// 前端私钥，用于解密后端加密的数据
const FRONT_PRIVATE_KEY = "ff3803fdaa6dbbc77f70f62d9bb1cfbc4c010c57c25fc44806d59f33b9a7f65a";

export const SM2Utils = {
  encrypt: function(data: string) {
    // sm-crypto 需要未压缩公钥（通常以 04 开头）
    const publicKey = BACK_PUBLIC_KEY.startsWith('04') ? BACK_PUBLIC_KEY : `04${BACK_PUBLIC_KEY}`;
    return sm2.doEncrypt(data, publicKey, 1); // 1表示C1C2C3模式
  },
  decrypt: function(encryptData: string) {
    // 使用前端私钥解密
    return sm2.doDecrypt(encryptData, FRONT_PRIVATE_KEY, 1); // 1表示C1C2C3模式
  }
};

// 导出单例实例
export const sm2Utils = SM2Utils;
