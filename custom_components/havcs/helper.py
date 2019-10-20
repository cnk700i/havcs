import logging
import copy
from homeassistant.helpers.state import AsyncTrackStates
from .const import STORAGE_VERSION, STORAGE_KEY, INTEGRATION

_LOGGER = logging.getLogger(__name__)
LOGGER_NAME = 'helper'

DOMAIN_SERVICE_WITHOUT_ENTITY_ID = ['climate']

class VoiceControlProcessor:
    def _discovery_process_propertites(self, device_properties) -> None:
        raise NotImplementedError()

    def _discovery_process_actions(self, device_properties, raw_actions) -> None:
        raise NotImplementedError()

    def _discovery_process_device_type(self, raw_device_type) -> None:
        raise NotImplementedError()

    def _discovery_process_device_info(self, entity_id, device_type, device_name, zone, properties, actions) -> None:
        raise NotImplementedError() 
  
    def _control_process_propertites(self, device_properties, action) -> None:
        raise NotImplementedError()

    def _query_process_propertites(self, device_properties, action) -> None:
        raise NotImplementedError()  

    def _prase_action_p2h(self, action) -> None:
        i = 0
        service = ''
        for c in action.split('Request')[0]:
            service += (('_' if i else '') + c.lower()) if c.isupper() else c
            i += 1
        return service

    def _decrypt_device_id(self, device_id) -> None:
        raise NotImplementedError()

    def _prase_command(self, command, arg) -> None:
        raise NotImplementedError()
    
    def _errorResult(self, errorCode, messsage=None) -> None:
        raise NotImplementedError()

    vcdm = None
    _hass = None
    _service_map_p2h = None
    def process_discovery_command(self) -> tuple:
        devices = []
        entity_ids = []
        for vc_device in self.vcdm.all(self._hass):
            entity_id, raw_device_type, device_name, zone, device_properties, raw_actions = self.vcdm.get_device_attrs(vc_device)
            properties = self._discovery_process_propertites(device_properties)
            actions = self._discovery_process_actions(device_properties, raw_actions)
            device_type = self._discovery_process_device_type(raw_device_type)
            if None in (device_type, device_name, zone) or [] in (properties, actions):
                _LOGGER.debug('[%s] can get all info of entity %s, pass. [device_type = %s, device_name = %s, zone = %s, properties = %s, actions = %s]', LOGGER_NAME, entity_id, device_type, device_name, zone, properties, actions)
            else:
                devices.append(self._discovery_process_device_info(entity_id, device_type, device_name, zone, properties, actions))
                entity_ids.append(entity_id)
        return None, devices, entity_ids

    async def process_control_command(self, command) -> tuple:
        device_id = self._prase_command(command, 'device_id')
        entity_id = self._decrypt_device_id(device_id)
        action = self._prase_command(command, 'action')
        domain = entity_id[:entity_id.find('.')]
        data = {"entity_id": entity_id }
        domain_list = [domain]
        data_list = [data]
        service_list =['']
        if domain in self._service_map_p2h.keys():
            translation = self._service_map_p2h[domain][action]
            if callable(translation):
                attributes = self._hass.data[INTEGRATION]['devices'].get(entity_id)
                state = self._hass.states.get(entity_id)
                domain_list, service_list, data_list = translation(state, attributes, self._prase_command(command, 'payload'))
                _LOGGER.debug('domain_list: %s', domain_list)
                _LOGGER.debug('service_list: %s', service_list)
                _LOGGER.debug('data_list: %s', data_list)
                for i,d in enumerate(data_list):
                    if 'entity_id' not in d and domain_list[i] not in DOMAIN_SERVICE_WITHOUT_ENTITY_ID:
                        d.update(data)
            else:
                service_list[0] = translation
        else:
            service_list[0] = self._prase_action_p2h(action)

        for i in range(len(domain_list)):
            _LOGGER.debug('domain: %s, servcie: %s, data: %s', domain_list[i], service_list[i], data_list[i])
            with AsyncTrackStates(self._hass) as changed_states:
                result = await self._hass.services.async_call(domain_list[i], service_list[i], data_list[i], True)
                _LOGGER.debug('changed_states: %s', changed_states)
            if not result:
                return self._errorResult('IOT_DEVICE_OFFLINE'), None
        device_properties = self.vcdm.get(entity_id).get('properties')
        properties = self._control_process_propertites(device_properties, action)
        return None, properties

    def process_query_command(self, command) -> tuple:
        device_id = self._prase_command(command, 'device_id')
        entity_id = self._decrypt_device_id(device_id)
        action = self._prase_command(command, 'action')
        device_properties = self.vcdm.get(entity_id).get('properties')
        properties = self._query_process_propertites(device_properties, action)
        return None if properties else self._errorResult('IOT_DEVICE_OFFLINE'), properties

class VoiceControlDeviceManager:

    def __init__(self, platform, device_action_map_h2p, device_attribute_map_h2p, service_map_p2h, device_type_map_h2p, device_type_alias, device_name_constraints = {}, zone_constraints = []):
        self._platform = platform
        self.device_action_map_h2p = device_action_map_h2p
        self.device_attribute_map_h2p = device_attribute_map_h2p
        self._service_map_p2h = service_map_p2h
        self.device_type_map_h2p = device_type_map_h2p
        self._device_type_alias = device_type_alias
        self._device_name_constraints = device_name_constraints
        self._zone_constraints = zone_constraints
        self._device_info_cache = {}
        self._places = ["门口","客厅","卧室","客房","主卧","次卧","书房","餐厅","厨房","洗手间","浴室","阳台",\
        "宠物房","老人房","儿童房","婴儿房","保姆房","玄关","一楼","二楼","三楼","四楼","楼梯","走廊",\
        "过道","楼上","楼下","影音室","娱乐室","工作间","杂物间","衣帽间","吧台","花园","温室","车库","休息室","办公室","起居室"]
    def all(self, hass = None, init_flag = False) -> list:
        if not self._device_info_cache or init_flag:
            self._device_info_cache.clear()
            for entity_id, attributes in hass.data[INTEGRATION]['devices'].items():
                if 'havcs_visable' not in attributes:
                    pass
                elif isinstance(attributes.get('havcs_visable') , str) and self._platform == attributes.get('havcs_visable'):
                    pass
                elif isinstance(attributes.get('havcs_visable') , list) and self._platform in attributes.get('havcs_visable'):
                    pass
                else:
                    continue
                self._device_info_cache.update(self.get(entity_id, hass, attributes))
        return list(self._device_info_cache.values())

    def get(self, entity_id, hass = None, attributes = None) -> dict:
        if attributes is None:
            return self._device_info_cache.get(entity_id, {})
        device_type = self.get_device_type(hass, entity_id, attributes)
        device_name = self.get_device_name(hass, entity_id, attributes, self._places, self._device_name_constraints)
        zone = self.get_device_zone(hass, entity_id, attributes, self._places, self._zone_constraints)
        actions = self.get_device_actions(entity_id, attributes, device_type)

        properties =[]
        if entity_id.startswith('sensor.'):
            related_entity_ids = attributes.get('havcs_related_sensors', [entity_id])
            sensor_ids = []
            for related_entity_id in related_entity_ids:
                if related_entity_id.startswith('group.'):
                    for entity_in_group_id in hass.states.get(related_entity_id).attributes.get('entity_id'):
                        if entity_in_group_id.startswith('sensor.'):
                            sensor_ids.append(entity_in_group_id)
                elif related_entity_id.startswith('sensor.'):
                    sensor_ids.append(related_entity_id)
                else:
                    pass 
            for sensor in sensor_ids:
                sensor_properties = self.get_device_properties(sensor, attributes)
                if sensor_properties :
                    actions += self.get_sensor_actions_from_properties(sensor_properties)
                    properties += sensor_properties
            actions = list(set(actions))
        else:
            properties = self.get_device_properties(entity_id, attributes)
        device_info = {
            'entity_id': entity_id,
            'device_type': device_type,
            'device_name': device_name,
            'zone': zone,
            'properties': properties,
            'actions': actions
        }
        return {entity_id:device_info}
 
    def get_device_attrs(self, device) -> list:
        return device.get('entity_id'),device.get('device_type'),device.get('device_name'),device.get('zone'),device.get('properties'),device.get('actions')

    def get_device_type(self, hass, entity_id, attributes) -> str:
        device_type = None

        if 'havcs_device_type' in attributes:
            device_type = self.device_type_map_h2p.get(attributes['havcs_device_type'])
            if device_type:
                return device_type
        # Guess from entity_id
        for device_type in self._device_type_alias.keys():
            if device_type.lower() in entity_id:
                return device_type

        # Guess from entity_id's domain
        device_type = self.device_type_map_h2p.get(entity_id[:entity_id.find('.')])

        # Guess from entity's friendlyname
        state = hass.states.get(entity_id)
        if device_type is None and state:
            for device_type, alias in self._device_type_alias.items():
                if alias in state.attributes.get('friendly_name'):
                    return device_type

        return device_type

    def get_device_name(self, hass, entity_id, attributes, places = [], device_name_constraints = []) -> str:
        device_name = None
        
        if 'havcs_device_name' in attributes:
            device_name = attributes['havcs_device_name']
        else:
            # Guess from friendly_name
            state = hass.states.get(entity_id)
            if state:
                device_name = state.attributes.get('friendly_name')

        if device_name_constraints and device_name:
            # Name validation
            for device_name_constraint in device_name_constraints:
                aliases = [device_name_constraint['key']]+ device_name_constraint['value']
                for alias in aliases:
                    if alias in device_name:
                        return alias
            return None
            
        return device_name

    def get_device_zone(self, hass, entity_id, attributes, places = [], zone_constraints = []) ->str:
        zone = '未指定'
        if 'havcs_zone' in attributes:
            zone = attributes['havcs_zone']
        else:
            device_name = attributes.get('havcs_device_name')
            # Guess from friendly_name
            state = hass.states.get(entity_id)
            if not device_name and state:
                device_name = state.attributes.get('friendly_name')

            if device_name:
                for place in places:
                    if  device_name.startswith(place):
                        zone = place
                        break
        if zone == '未指定':
            # Guess from HomeAssistant group which contains entity 
            for state in hass.states.async_all():
                group_entity_id = state.entity_id
                if group_entity_id.startswith('group.') and not group_entity_id.startswith('group.all_') and group_entity_id != 'group.default_view':
                    if entity_id in state.attributes.get('entity_id'):
                        for place in places:
                            if place in state.attributes.get('friendly_name'):
                                zone = place
                                break
        if zone_constraints:
            return zone if zone in zone_constraints else None
        else:
            return zone

    def get_device_properties(self, entity_id, attributes) -> list:
        properties = []
        if 'havcs_attributes' in attributes:
            for attribute in attributes['havcs_attributes']:
                properties.append({'entity_id': entity_id, 'attribute': attribute})
        elif entity_id.startswith('sensor.'):
            unit = attributes.get('unit_of_measurement', '')
            if unit == u'°C' or unit == u'℃':
                attribute = 'temperature'
            elif unit == 'lx' or unit == 'lm':
                attribute = 'brightness'
            elif ('temperature' in entity_id):
                attribute = 'temperature'
            elif ('humidity' in entity_id):
                attribute = 'humidity'
            elif ('pm25' in entity_id):
                attribute = 'pm25'
            elif ('co2' in entity_id):
                attribute = 'co2'
            else:
                attribute = []
                _LOGGER.debug('[%s] unsupport sensor %s', LOGGER_NAME, entity_id)
            if attribute:
                properties = [{'entity_id': entity_id, 'attribute': attribute}]
            else:
                properties = []
        else:
            properties = [{'entity_id': entity_id, 'attribute': 'power_state'}]
        return properties
    
    def get_property_related_entity_id(self, attribute, properties):
        for device_property in properties:
            if attribute == device_property.get('attribute'):
                return device_property.get('entity_id')

    def format_property(self, hass, device_properties, format_template):
        formatted_property = copy.deepcopy(format_template)
        for key in formatted_property:
            if '%' in formatted_property[key]:
                attribute = formatted_property[key][1:]
                entity_id = self.get_property_related_entity_id(attribute, device_properties)
                formatted_property[key] = hass.states.get(entity_id).state
        return formatted_property

    def get_device_actions(self, entity_id, attributes, device_type) -> list:
        if 'havcs_actions' in attributes:
            # actions = [AIHOME_ACTIONS_ALIAS[DOMAIN].get(action) for action in attributes['havcs_actions'].keys() if AIHOME_ACTIONS_ALIAS[DOMAIN].get(action)]
            action = attributes['havcs_actions']
        elif device_type == 'switch':
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif device_type == 'light':
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "set_brightness", "increase_brightness", "decrease_brightness", "set_color"]
        elif device_type == 'cover':
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "pause"]
        elif device_type == 'vacuum':
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif device_type == 'sensor':
            action = ["query"]
        elif entity_id.startswith('switch.'):
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif entity_id.startswith('light.'):
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "set_brightness", "increase_brightness", "decrease_brightness", "set_color"]
        elif entity_id.startswith('cover.'):
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "pause"]
        elif entity_id.startswith('vacuum.'):
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif entity_id.startswith('sensor.'):
            action = ["query"]
        else:
            action = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        return action
    
    def get_sensor_actions_from_properties(self, properties) -> list:
        return [ 'query_' + device_property.get('attribute') for device_property in properties]
    
# 用于管理哪些平台哪些用户有哪些设备
class BindManager:
    _privious_upload_devices = {}
    _new_upload_devices = {}
    _discovery = set()
    def __init__(self, hass, platforms):
        _LOGGER.debug('[bindManager] ----init bindManager----')
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
            _LOGGER.debug('[bindManager] discovery:\n%s', self.discovery)
    def get_bind_entity_ids(self, platform, p_user_id = '', repeat_upload = True):
        _LOGGER.debug('[bindManager] privious_upload_devices:\n%s', self._privious_upload_devices)
        _LOGGER.debug('[bindManager] new_upload_devices:\n%s', self._new_upload_devices.get(platform))
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
        # _LOGGER.debug('[bindManager]  0.linked_account:%s', linked_account)
        for entity_id in devices:
            if entity_id in self._new_upload_devices.get(platform):
                device =  self._new_upload_devices.get(platform).get(entity_id)
                device['linked_account'] = device['linked_account'] | linked_account
                # _LOGGER.debug('[bindManager]  1.linked_account:%s', device['linked_account'])
            else:
                linked_account =linked_account | set(['@' + platform for pplatform in platform])
                device = {
                    'entity_id': entity_id,
                    'linked_account': linked_account,
                }
                # _LOGGER.debug('[bindManager]  1.linked_account:%s', device['linked_account'])
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
        _LOGGER.debug('[bindManager]  all_unbind_devices:\n%s',devices)

        upload_devices  = [
            {
            'entity_id': entity_id,
            'linked_account': list((self._privious_upload_devices.get(entity_id,{}).get('linked_account',set()) | self._new_upload_devices.get(platform).get(entity_id,{}).get('linked_account',set())) - devices.get(entity_id,{}).get('linked_account',set()))
            } for entity_id in set(list(self._privious_upload_devices.keys())+list(self._new_upload_devices.get(platform).keys()))
        ]
        _LOGGER.debug('[bindManager] upload_devices:\n%s',upload_devices)
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
            # _LOGGER.debug('[bindManager] 用户(%s)已执行discovery', uid)
            bind_entity_ids = []
            unbind_entity_ids = []
        else:
            # _LOGGER.debug('用户(%s)启动首次执行discovery', uid)
            self.add_discovery(uid)
            bind_entity_ids = self.get_bind_entity_ids(platform = platform,p_user_id =p_user_id, repeat_upload = False)
            unbind_entity_ids = self.get_unbind_entity_ids(platform = platform,p_user_id=p_user_id)
            await self.async_save(platform, p_user_id=p_user_id)
        # _LOGGER.debug('[bindManager] p_user_id:%s',p_user_id)
        # _LOGGER.debug('[bindManager] get_bind_entity_ids:%s', bind_entity_ids)
        # _LOGGER.debug('[bindManager] get_unbind_entity_ids:%s', unbind_entity_ids)
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
        # _LOGGER.debug('[bindManager] %s', self._discovery)
        # _LOGGER.debug('[bindManager] %s', self._privious_upload_devices)
        p_user_ids = []
        for uid in self._discovery:
            p_user_id = uid.split('@')[0]
            p = uid.split('@')[1]
            if p == platform and (set([uid, '*@' + platform]) & self._privious_upload_devices.get(entity_id,{}).get('linked_account',set())):
                p_user_ids.append(p_user_id)
        return p_user_ids