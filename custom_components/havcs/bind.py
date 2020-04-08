import json
import aiohttp
import asyncio
import async_timeout
import logging
import traceback

from homeassistant.const import EVENT_STATE_CHANGED, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import HAVCS_SERVICE_URL, DATA_HAVCS_HANDLER, DATA_HAVCS_BIND_MANAGER, STORAGE_VERSION, INTEGRATION
from . import util as havcs_util

_LOGGER = logging.getLogger(__name__)
LOGGER_NAME = 'bind'

STORAGE_KEY='havcs_bind_manager'
STORAGE_VERSION

# 用于管理哪些平台哪些用户有哪些设备
class HavcsBindManager:
    _privious_upload_devices = {}
    _new_upload_devices = {}
    _discovery = set()
    def __init__(self, hass, platforms, bind_device = False, sync_device = False, app_key = None, decrypt_key = None):
        _LOGGER.debug("[bindManager] ----init bindManager----")
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._platforms = platforms
        for platform in platforms:
            self._new_upload_devices[platform] = {}
        self._hass = hass
        self._sync_manager = {
            'bind_device': bind_device,
            'sync_device': sync_device,
            'app_key': app_key,
            'decrypt_key': decrypt_key
        }
    async def async_init(self):
        await self.async_load()
        if self._sync_manager.get('bind_device'):
            await self.async_bind_device()
        if self._sync_manager.get('sync_device'):
            self.sync_device()

    async def async_load(self):
        data =  await self._store.async_load()  # load task config from disk
        if data:
            self._privious_upload_devices = {
                device['device_id']: {'device_id': device['device_id'], 'linked_account': set(device['linked_account'])} for device in data.get('upload_devices',[])
            }
            self._discovery = set(data.get('discovery',[]))
            _LOGGER.debug("[bindManager] discovery:\n%s", self.discovery)

    def get_bind_entity_ids(self, platform, p_user_id = '', repeat_upload = True):
        _LOGGER.debug("[bindManager] privious_upload_devices:\n%s", self._privious_upload_devices)
        _LOGGER.debug("[bindManager] new_upload_devices:\n%s", self._new_upload_devices.get(platform))
        search = set([p_user_id + '@' + platform, '*@' + platform]) # @jdwhale获取平台所有设备，*@jdwhale表示该不限定用户
        if repeat_upload:
            bind_entity_ids = [device['device_id'] for device in self._new_upload_devices.get(platform).values() if search & device['linked_account'] ]
        else:
            bind_entity_ids = [device['device_id'] for device in self._new_upload_devices.get(platform).values() if (search & device['linked_account']) and not(search & self._privious_upload_devices.get(device['device_id'],{}).get('linked_account',set()))]
        return bind_entity_ids
    
    def get_unbind_entity_ids(self, platform, p_user_id = ''):
        search = set([p_user_id + '@' + platform, '*@' + platform])
        unbind_devices = [device['device_id'] for device in self._privious_upload_devices.values() if (search & device['linked_account']) and not(search & self._new_upload_devices.get(platform).get(device['device_id'],{}).get('linked_account',set()))]
        return unbind_devices

    def update_lists(self, devices, platform, p_user_id= '*',repeat_upload = True):
        if platform is None:
            platforms = [platform for platform in self._platforms]
        else:
            platforms = [platform]

        linked_account = set([p_user_id + '@' + platform for platform in platforms])
        # _LOGGER.debug("[bindManager]  0.linked_account:%s", linked_account)
        for device_id in devices:
            if device_id in self._new_upload_devices.get(platform):
                device =  self._new_upload_devices.get(platform).get(device_id)
                device['linked_account'] = device['linked_account'] | linked_account
                # _LOGGER.debug("[bindManager]  1.linked_account:%s", device['linked_account'])
            else:
                linked_account =linked_account | set(['@' + platform for pplatform in platform])
                device = {
                    'device_id': device_id,
                    'linked_account': linked_account,
                }
                # _LOGGER.debug("[bindManager]  1.linked_account:%s", device['linked_account'])
                self._new_upload_devices.get(platform)[device_id] = device

    async def async_save(self, platform, p_user_id= '*'):
        devices = {}         
        for device_id in self.get_unbind_entity_ids(platform, p_user_id):
            if device_id in devices:
                device =  devices.get(device_id)
                device['linked_account'] = device['linked_account'] | linked_account
                # _LOGGER.debug("1.linked_account:%s", device['linked_account'])
            else:
                linked_account =set([p_user_id +'@'+platform])
                device = {
                    'device_id': device_id,
                    'linked_account': linked_account,
                }
                # _LOGGER.debug("1.linked_account:%s", device['linked_account'])
                devices[device_id] = device
        _LOGGER.debug("[bindManager]  all_unbind_devices:\n%s", devices)

        upload_devices  = [
            {
            'device_id': device_id,
            'linked_account': list((self._privious_upload_devices.get(device_id,{}).get('linked_account',set()) | self._new_upload_devices.get(platform).get(device_id,{}).get('linked_account',set())) - devices.get(device_id,{}).get('linked_account',set()))
            } for device_id in set(list(self._privious_upload_devices.keys())+list(self._new_upload_devices.get(platform).keys()))
        ]
        _LOGGER.debug("[bindManager] upload_devices:\n%s", upload_devices)
        data = {
            'upload_devices':upload_devices,
            'discovery':self.discovery
        }
        await self._store.async_save(data)
        self._privious_upload_devices = {
                    device['device_id']: {'device_id': device['device_id'], 'linked_account': set(device['linked_account'])} for device in upload_devices
            }

    async def async_save_changed_devices(self, new_devices, platform, p_user_id = '*', force_save = False):
        self.update_lists(new_devices, platform)
        uid = p_user_id+'@'+platform
        if self.check_discovery(uid) and not force_save:
            # _LOGGER.debug("[bindManager] 用户(%s)已执行discovery", uid)
            bind_entity_ids = []
            unbind_entity_ids = []
        else:
            # _LOGGER.debug("用户(%s)启动首次执行discovery", uid)
            self.add_discovery(uid)
            bind_entity_ids = self.get_bind_entity_ids(platform = platform,p_user_id =p_user_id, repeat_upload = False)
            unbind_entity_ids = self.get_unbind_entity_ids(platform = platform,p_user_id=p_user_id)
            await self.async_save(platform, p_user_id=p_user_id)
        # _LOGGER.debug("[bindManager] p_user_id:%s',p_user_id)
        # _LOGGER.debug("[bindManager] get_bind_entity_ids:%s", bind_entity_ids)
        # _LOGGER.debug("[bindManager] get_unbind_entity_ids:%s", unbind_entity_ids)
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

    def get_uids(self, platform, device_id):
        # _LOGGER.debug("[bindManager] %s", self._discovery)
        # _LOGGER.debug("[bindManager] %s", self._privious_upload_devices)
        p_user_ids = []
        for uid in self._discovery:
            p_user_id = uid.split('@')[0]
            p = uid.split('@')[1]
            if p == platform and (set([uid, '*@' + platform]) & self._privious_upload_devices.get(device_id,{}).get('linked_account',set())):
                p_user_ids.append(p_user_id)
        return p_user_ids

    async def async_bind_device(self):
        for uuid in self._hass.data[INTEGRATION][DATA_HAVCS_BIND_MANAGER].discovery:
            p_user_id = uuid.split('@')[0]
            platform = uuid.split('@')[1]
            if platform in self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER] and getattr(self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER].get(platform), 'should_report_when_starup', False) and hasattr(self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER].get(platform), 'bind_device'):
                err_result, devices, entity_ids = self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER][platform].process_discovery_command()
                if err_result:
                    return
                bind_entity_ids, unbind_entity_ids = await self._hass.data[INTEGRATION][DATA_HAVCS_BIND_MANAGER].async_save_changed_devices(entity_ids,platform, p_user_id,True)
                payload = await self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER][platform].bind_device(p_user_id, entity_ids , unbind_entity_ids, devices)
                _LOGGER.debug("[skill] bind device to %s:\nbind_entity_ids = %s, unbind_entity_ids = %s", platform, bind_entity_ids, unbind_entity_ids)

                if payload:
                    url = HAVCS_SERVICE_URL + '/skill/smarthome.php?v=update&AppKey='+self._sync_manager.get('app_key')
                    data = havcs_util.AESCipher(self._sync_manager.get('decrypt_key')).encrypt(json.dumps(payload, ensure_ascii = False).encode('utf8'))
                    try:
                        session = async_get_clientsession(self._hass, verify_ssl=False)
                        with async_timeout.timeout(5, loop=self._hass.loop):
                            response = await session.post(url, data=data)
                            _LOGGER.debug("[skill] get bind device result from %s: %s", platform, await response.text())
                    except(asyncio.TimeoutError, aiohttp.ClientError):
                        _LOGGER.error("[skill] fail to access %s, bind device fail: timeout", url)
                    except:
                        _LOGGER.error("[skill] fail to access %s, bind device fail: %s", url, traceback.format_exc())
    
    def sync_device(self):
        remove_listener = self._sync_manager.get('remove_listener')
        if remove_listener:
            remove_listener()
    
        @callback
        def report_device(event):
            # _LOGGER.debug("[skill] %s changed, try to report", event.data[ATTR_ENTITY_ID])
            self._hass.add_job(async_report_device(event))

        async def async_report_device(event):
            """report device state when changed. """
            entity = self._hass.states.get(event.data[ATTR_ENTITY_ID])
            if entity is None:
                return
            for platform, handler in self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER].items():
                if hasattr(handler, 'report_device'):
                    device_ids = handler.vcdm.get_entity_related_device_ids(self._hass, entity.entity_id)
                    for device_id in device_ids:
                        payload = handler.report_device(device_id)
                        _LOGGER.debug("[skill] report device to %s: platform = %s, device_id = %s (entity_id = %s), data = %s", platform, device_id, event.data[ATTR_ENTITY_ID], platform, payload)
                        if payload:
                            url = HAVCS_SERVICE_URL + '/skill/'+platform+'.php?v=report&AppKey=' + self._sync_manager.get('app_key')
                            data = havcs_util.AESCipher(self._sync_manager.get('decrypt_key')).encrypt(json.dumps(payload, ensure_ascii = False).encode('utf8'))
                            try:
                                session = async_get_clientsession(self._hass, verify_ssl=False)
                                with async_timeout.timeout(5, loop=self._hass.loop):
                                    response = await session.post(url, data=data)
                                    _LOGGER.debug("[skill] get report device result from %s: %s", platform, await response.text())
                            except(asyncio.TimeoutError, aiohttp.ClientError):
                                _LOGGER.error("[skill] fail to access %s, report device fail: timeout", url)
                            except:
                                _LOGGER.error("[skill] fail to access %s, report device fail: %s", url, traceback.format_exc())
        
        self._sync_manager['remove_listener'] = self._hass.bus.async_listen(EVENT_STATE_CHANGED, report_device)

    def clear(self):
        remove_listener = self._sync_manager.get('remove_listener')
        if remove_listener:
            remove_listener() 