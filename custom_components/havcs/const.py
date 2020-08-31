"""Constants used by havcs."""
HAVCS_SERVICE_URL = 'https://havcs.ljr.im:8123'

ATTR_DEVICE_VISABLE  = 'visable'
ATTR_DEVICE_ID = 'device_id'
ATTR_DEVICE_ENTITY_ID = 'entity_id'
ATTR_DEVICE_TYPE = 'type'
ATTR_DEVICE_NAME = 'name'
ATTR_DEVICE_ZONE = 'zone'
ATTR_DEVICE_ICON = 'icon'
ATTR_DEVICE_ATTRIBUTES = 'attributes'
ATTR_DEVICE_ACTIONS  = 'actions'
ATTR_DEVICE_PROPERTIES = 'properties'

DATA_HAVCS_CONFIG = 'config'
DATA_HAVCS_MQTT = 'mqtt'
DATA_HAVCS_BIND_MANAGER = 'bind_manager'
DATA_HAVCS_HTTP_MANAGER = 'http_manager'
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
CONF_DEVICE_CONFIG = 'device_config'
CONF_DEVICE_CONFIG_PATH = 'device_config_path'

CONF_MODE = 'mode'

CLIENT_PALTFORM_DICT = {
    'jdwhale': 'https://alphadev.jd.com',
    'dueros': 'https://xiaodu.baidu.com',
    'aligenie': 'https://open.bot.tmall.com'
}

HAVCS_ACTIONS_ALIAS = {
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
    },
    'jdwhale':{
        'turn_on': 'TurnOn',
        'turn_off': 'TurnOff',
        'increase_brightness': 'AdjustUpBrightness',
        'decrease_brightness': 'AdjustDownBrightness'
    }
}

DEVICE_PLATFORM_DICT = {
    'aligenie': {
        'cn_name': '天猫精灵'
    },
    'dueros': {
        'cn_name': '小度'
    },
    'jdwhale': {
        'cn_name': '小京鱼'
    },
    'weixin': {
        'cn_name': '企业微信'
    }
}
DEVICE_TYPE_DICT = {
    'climate': {
        'cn_name': '空调',
        'icon': 'mdi-air-conditioner'
    },
    'fan': {
        'cn_name': '风扇',
        'icon': 'mdi-pinwheel'
    },
    'light': {
        'cn_name': '灯',
        'icon': 'mdi-lightbulb'
    },
    'media_player': {
        'cn_name': '播放器',
        'icon': 'mdi-television-classic'
    },
    'switch': {
        'cn_name': '开关',
        'icon': 'mdi-toggle-switch'
    },
    'sensor': {
        'cn_name': '传感器',
        'icon': 'mdi-access-point-network'
    },
    'cover': {
        'cn_name': '窗帘',
        'icon': 'mdi-window-shutter'
    },
    'vacuum': {
        'cn_name': '扫地机',
        'icon': 'mdi-robot-vacuum-variant'
    }
}
DEVICE_ACTION_DICT ={
    'turn_on': {
        'cn_name': '打开'
    },
    'turn_off': {
        'cn_name': '关闭'
    },
    'timing_turn_on': {
        'cn_name': '延时打开'
    },
    'timing_turn_off': {
        'cn_name': '延时关闭'
    },
    'query_temperature': {
        'cn_name': '查询温度'
    },
    'query_humidity': {
        'cn_name': '查询湿度'
    },
    'increase_brightness': {
        'cn_name': '调高亮度'
    },
    'decrease_brightness': {
        'cn_name': '调低亮度'
    }
}

DEVICE_ATTRIBUTE_DICT = {
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