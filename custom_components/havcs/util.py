from Crypto.Cipher import AES
from base64 import b64decode
from base64 import b64encode
import homeassistant.util.color as color_util
import time
import logging
import re
import jwt
from typing import cast


_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)
LOGGER_NAME = 'util'





bindManager = None
ENTITY_KEY = ''
CONTEXT_AIHOME = None
EXPIRATION = {}
class AESCipher:
    """
    Tested under Python 3.x and PyCrypto 2.6.1.
    """
    def __init__(self, key):
        #加密需要的key值
        self.key=key
        self.mode = AES.MODE_CBC
    def encrypt(self, raw):
        # Padding for the input string --not
        # related to encryption itself.
        BLOCK_SIZE = 16  # Bytes
        pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * \
                        chr(BLOCK_SIZE - len(s) % BLOCK_SIZE).encode('utf8')
        raw = pad(raw)
        #通过key值，使用ECB模式进行加密
        cipher = AES.new(self.key, self.mode, b'0000000000000000')
        #返回得到加密后的字符串进行解码然后进行64位的编码
        return b64encode(cipher.encrypt(raw)).decode('utf8')

    def decrypt(self, enc):
        unpad = lambda s: s[:-ord(s[len(s) - 1:])]
        #首先对已经加密的字符串进行解码
        enc = b64decode(enc)
        #通过key值，使用ECB模式进行解密
        cipher = AES.new(self.key, self.mode, b'0000000000000000')
        return unpad(cipher.decrypt(enc)).decode('utf8')

def decrypt_device_id(device_id):
    try:
        if not ENTITY_KEY:
            entity_id = device_id
        else:
            device_id = device_id.replace('-', '+')
            device_id = device_id.replace('_', '/')
            pad4 = '===='
            device_id += pad4[0:len(device_id) % 4]
            entity_id = AESCipher(ENTITY_KEY.encode('utf-8')).decrypt(device_id)
    except:
        entity_id = None
    finally:
        return entity_id
def encrypt_entity_id(entity_id):
    if not ENTITY_KEY:
        device_id = entity_id
    else:
        device_id = AESCipher(ENTITY_KEY.encode('utf-8')).encrypt(entity_id.encode('utf8'))
        device_id = device_id.replace('+', '-')
        device_id = device_id.replace('/', '_')
        device_id = device_id.replace('=', '')
    return device_id

def hsv2rgb(hsvColorDic):

    h = float(hsvColorDic['hue'])
    s = float(hsvColorDic['saturation'])
    v = float(hsvColorDic['brightness'])
    rgb = color_util.color_hsv_to_RGB(h, s, v)

    return rgb

def timestamp2Delay(timestamp):
    delay = abs(int(time.time()) - timestamp)
    return delay

def get_platform_from_command(command):
    if 'AliGenie' in command:
        platform = 'aligenie'
    elif 'DuerOS' in command:
        platform = 'dueros'
    elif 'Alpha' in command:
        platform = 'jdwhale'
    else:
        platform = 'unknown'
    return platform

def get_token_from_command(command):
    result = re.search(r'(?:accessToken|token)[\'\"\s:]+(.*?)[\'\"\s]+(,|\})', command, re.M|re.I)
    return result.group(1) if result else None

async def async_update_token_expiration(access_token, hass, expiration):
    try:
        unverif_claims = jwt.decode(access_token, verify=False)
        refresh_token = await hass.auth.async_get_refresh_token(cast(str, unverif_claims.get('iss')))
        for user in hass.auth._store._users.values():
            if refresh_token.id in user.refresh_tokens and refresh_token.access_token_expiration != expiration:
                _LOGGER.debug('[util] set new access token expiration for refresh_token[%s]', refresh_token.id)
                refresh_token.access_token_expiration = expiration
                user.refresh_tokens[refresh_token.id] = refresh_token
                hass.auth._store._async_schedule_save()
                break
    except jwt.InvalidTokenError:
        _LOGGER.debug('[util] access_token[%s] is invalid, try another reauthorization on website.', access_token)