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

STORAGE_VERSION = 1
STORAGE_KEY = 'aihome'

DOMAIN_SERVICE_WITHOUT_ENTITY_ID = ['climate']
AIHOME_ACTIONS_ALIAS = {
    'jdwhale':{
        'turn_on': 'TurnOn',
        'turn_off': 'TurnOff',
        'increase_brightness': 'AdjustUpBrightness',
        'decrease_brightness': 'AdjustDownBrightness'
    },
    'aligenie':{
        'turn_on': 'turnOn',
        'turn_off': 'turnOff',
        'increase_brightness': 'incrementBrightnessPercentage',
        'decrease_brightness': 'decrementBrightnessPercentage'
    },
    'dueros':{
        'turn_on': 'TurnOn',
        'turn_off': 'TurnOff',
        'increase_brightness': 'AdjustUpBrightness',
        'decrease_brightness': 'AdjustDownBrightness'
    }
}

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

# 用于管理哪些平台哪些用户有哪些设备
class BindManager:
    _privious_upload_devices = {}
    _new_upload_devices = {}
    _discovery = set()
    def __init__(self, hass, platforms):
        _LOGGER.debug('----init bindMansger----')
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._platforms = platforms
        for platform in platforms:
            self._new_upload_devices[platform]={}
    
    async def async_load(self):
        data =  await self._store.async_load()  # load task config from disk
        if data:
            self._privious_upload_devices = {
                    device['entity_id']: {'entity_id': device['entity_id'], 'linked_account': set(device['linked_account'])} for device in data.get('upload_devices',[])
            }
            self._discovery = set(data.get('discovery',[]))
            _LOGGER.debug('discovery:%s', self.discovery)
    def get_bind_entity_ids(self, platform, p_user_id = '', repeat_upload = True):
        _LOGGER.debug('privious_upload_devices:%s', self._privious_upload_devices)
        _LOGGER.debug('new_upload_devices:%s', self._new_upload_devices.get(platform))
        search = set([p_user_id + '@' + platform, '*@' + platform]) # @jdwhale获取平台所有设备，*@jdwhale表示该不限定用户
        if repeat_upload:
            bind_entity_ids = [device['entity_id'] for device in self._new_upload_devices.get(platform).values() if search & device['linked_account'] ]
        else:
            bind_entity_ids = [device['entity_id'] for device in self._new_upload_devices.get(platform).values() if (search & device['linked_account']) and not(search & self._privious_upload_devices.get(device['entity_id'],{}).get('linked_account',set()))]
        return bind_entity_ids
    
    def get_unbind_entity_ids(self, platform, p_user_id = ''):
        search = set([p_user_id + '@' + platform, '*@' + platform])
        unbind_devices = [device['entity_id'] for device in self._privious_upload_devices.values() if (search & device['linked_account']) and not(search & self._new_upload_devices.get(platform).get(device['entity_id'],{}).get('linked_account',set()))]
        return unbind_devices

    def update_lists(self, devices, platform, p_user_id= '*',repeat_upload = True):
        if platform is None:
            platforms = [platform for platform in self._platforms]
        else:
            platforms = [platform]

        linked_account = set([p_user_id + '@' + platform for platform in platforms])
        # _LOGGER.debug('0.linked_account:%s', linked_account)
        for entity_id in devices:
            if entity_id in self._new_upload_devices.get(platform):
                device =  self._new_upload_devices.get(platform).get(entity_id)
                device['linked_account'] = device['linked_account'] | linked_account
                # _LOGGER.debug('1.linked_account:%s', device['linked_account'])
            else:
                linked_account =linked_account | set(['@' + platform for pplatform in platform])
                device = {
                    'entity_id': entity_id,
                    'linked_account': linked_account,
                }
                # _LOGGER.debug('1.linked_account:%s', device['linked_account'])
                self._new_upload_devices.get(platform)[entity_id] = device

    async def async_save(self, platform, p_user_id= '*'):
        devices = {}         
        for entity_id in self.get_unbind_entity_ids(platform, p_user_id):
            if entity_id in devices:
                device =  devices.get(entity_id)
                device['linked_account'] = device['linked_account'] | linked_account
                # _LOGGER.debug('1.linked_account:%s', device['linked_account'])
            else:
                linked_account =set([p_user_id +'@'+platform])
                device = {
                    'entity_id': entity_id,
                    'linked_account': linked_account,
                }
                # _LOGGER.debug('1.linked_account:%s', device['linked_account'])
                devices[entity_id] = device
        _LOGGER.debug('all_unbind_devices:%s',devices)

        upload_devices  = [
            {
            'entity_id': entity_id,
            'linked_account': list((self._privious_upload_devices.get(entity_id,{}).get('linked_account',set()) | self._new_upload_devices.get(platform).get(entity_id,{}).get('linked_account',set())) - devices.get(entity_id,{}).get('linked_account',set()))
            } for entity_id in set(list(self._privious_upload_devices.keys())+list(self._new_upload_devices.get(platform).keys()))
        ]
        _LOGGER.debug('upload_devices:%s',upload_devices)
        data = {
            'upload_devices':upload_devices,
            'discovery':self.discovery
        }
        await self._store.async_save(data)
        self._privious_upload_devices = {
                    device['entity_id']: {'entity_id': device['entity_id'], 'linked_account': set(device['linked_account'])} for device in upload_devices
            }

    async def async_save_changed_devices(self, new_devices, platform, p_user_id = '*', force_save = False):
        self.update_lists(new_devices, platform)
        uid = p_user_id+'@'+platform
        if self.check_discovery(uid) and not force_save:
            # _LOGGER.debug('用户(%s)已执行discovery', uid)
            bind_entity_ids = []
            unbind_entity_ids = []
        else:
            # _LOGGER.debug('用户(%s)启动首次执行discovery', uid)
            self.add_discovery(uid)
            bind_entity_ids = self.get_bind_entity_ids(platform = platform,p_user_id =p_user_id, repeat_upload = False)
            unbind_entity_ids = self.get_unbind_entity_ids(platform = platform,p_user_id=p_user_id)
            await self.async_save(platform, p_user_id=p_user_id)
        # _LOGGER.debug('p_user_id:%s',p_user_id)
        # _LOGGER.debug('get_bind_entity_ids:%s', bind_entity_ids)
        # _LOGGER.debug('get_unbind_entity_ids:%s', unbind_entity_ids)
        return bind_entity_ids,unbind_entity_ids

    def check_discovery(self, uid):
        if uid in self._discovery:
            return True
        else:
            return False
    def add_discovery(self, uid):
        self._discovery = self._discovery | set([uid])

    @property
    def discovery(self):
        return list(self._discovery)

    def get_uids(self, platform, entity_id):
        # _LOGGER.debug(self._discovery)
        # _LOGGER.debug(self._privious_upload_devices)
        p_user_ids = []
        for uid in self._discovery:
            p_user_id = uid.split('@')[0]
            p = uid.split('@')[1]
            if p == platform and (set([uid, '*@' + platform]) & self._privious_upload_devices.get(entity_id,{}).get('linked_account',set())):
                p_user_ids.append(p_user_id)
        return p_user_ids

def decrypt_device_id(device_id):
    if not ENTITY_KEY:
        return device_id
    device_id = device_id.replace('-', '+')
    device_id = device_id.replace('_', '/')
    pad4 = '===='
    device_id += pad4[0:len(device_id) % 4]
    entity_id = AESCipher(ENTITY_KEY.encode('utf-8')).decrypt(device_id)
    return entity_id
def encrypt_entity_id(entity_id):
    if not ENTITY_KEY:
        return entity_id
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
                _LOGGER.debug('[util] set new expiration for refresh_token[%s]', refresh_token.id)
                refresh_token.access_token_expiration = expiration
                user.refresh_tokens[refresh_token.id] = refresh_token
                hass.auth._store._async_schedule_save()
                break
    except jwt.InvalidTokenError:
        _LOGGER.debug('[util] access_token[%s] is invalid, try another reauthorization on website.', access_token)
