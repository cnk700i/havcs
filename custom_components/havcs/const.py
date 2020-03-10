"""Constants used by multiple MQTT modules."""
HAVCS_SERVICE_URL = 'https://havcs.ljr.im:8123'

ATTR_DEVICE_VISABLE  = 'visable'
ATTR_DEVICE_ID = 'device_id'
ATTR_DEVICE_ENTITY_ID = 'entity_id'
ATTR_DEVICE_TYPE = 'type'
ATTR_DEVICE_NAME = 'name'
ATTR_DEVICE_ZONE = 'zone'
ATTR_DEVICE_ATTRIBUTES = 'attributes'
ATTR_DEVICE_ACTIONS  = 'actions'
ATTR_DEVICE_PROPERTIES = 'properties'

DATA_HAVCS_CONFIG = 'config'
DATA_HAVCS_MQTT = 'mqtt'
DATA_HAVCS_BIND_MANAGER = 'bind_manager'
DATA_HAVCS_ITEMS = 'items'
DATA_HAVCS_HANDLER = 'handler'

CONF_BROKER = 'broker'
CONF_DISCOVERY = 'discovery'
DEFAULT_DISCOVERY = False
INTEGRATION = 'havcs'
STORAGE_VERSION = 1
STORAGE_KEY = 'havcs'

CONF_ENTITY_KEY = 'entity_key'
CONF_APP_KEY = 'app_key'
CONF_APP_SECRET = 'app_secret'
CONF_URL  = 'url'
CONF_PROXY_URL = 'proxy_url'
CONF_SKIP_TEST  = 'skip_test'

CONF_MODE = 'mode'
CONF_PLATFORM_ALIGENIE = 'aligenie'
CONF_PLATFORM_DUEROS = 'dueros'
CONF_PLATFORM_JDWHALE = 'jdwhale'
CONF_PLATFORM_WEIXIN = 'weixin'

PLATFORM_ALIAS = {
    CONF_PLATFORM_ALIGENIE: '天猫精灵',
    CONF_PLATFORM_DUEROS: '小度',
    CONF_PLATFORM_JDWHALE: '小京鱼',
    CONF_PLATFORM_WEIXIN: '企业微信'    
}

HAVCS_ACTIONS_ALIAS = {
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
        'turn_on': 'turnOn',
        'turn_off': 'turnOff',
        'increase_brightness': 'AdjustUpBrightness',
        'decrease_brightness': 'AdjustDownBrightness',
        'timing_turn_on': 'timingTurnOn',
        'timing_turn_off': 'timingTurnOff'
    }
}

DEVICE_PLATFORM_LIST = ['aligenie', 'dueros', 'jdwhale', 'weixin']
DEVICE_TYPE_LIST = ['climate', 'fan', 'light', 'media_player', 'switch', 'sensor', 'cover', 'vacuum']
DEVICE_ATTRIBUTE_LIST = ['temperature', 'brightness', 'humidity', 'pm25', 'co2', 'power_state']
DEVICE_ACTION_LIST = ['turn_on', 'turn_off', 'timing_turn_on', 'timing_turn_off', 'query_temperature', 'query_humidity', 'increase_brightness', 'decrease_brightness']

PROPERTY_DICT = {
    'temperature': {
        'scale': '°C',
        'legalValue': 'DOUBLE',
        'cn_name': '温度'
    },
    'brightness': {
        'scale': '%',
        'legalValue': '[0.0, 100.0]',
        'cn_name': '亮度'
    },
    'illumination': {
        'scale': 'lm',
        'legalValue': '[0.0, 1000.0]',
        'cn_name': '照度'
    },
    'humidity': {
        'scale': '%',
        'legalValue': '[0.0, 100.0]',
        'cn_name': '湿度'
    },
    'formaldehyde': {
        'scale': 'mg/m3',
        'legalValue': 'DOUBLE',
        'cn_name': '甲醛浓度'
    },
    'pm25': {
        'scale': 'μg/m3',
        'legalValue': '[0.0, 1000.0]',
        'cn_name': 'PM2.5浓度'
    },
    'co2': {
        'scale': 'ppm',
        'legalValue': 'INTEGER',
        'cn_name': '二氧化碳浓度'
    },
    'power_state': {
        'scale': '',
        'legalValue': '(on, off)',
        'cn_name': '电源'
    }   
}