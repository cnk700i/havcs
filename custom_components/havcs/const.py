"""Constants used by multiple MQTT modules."""
CONF_BROKER = 'broker'
CONF_DISCOVERY = 'discovery'
DEFAULT_DISCOVERY = False
INTEGRATION = 'havcs'
STORAGE_VERSION = 1
STORAGE_KEY = 'havcs'

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