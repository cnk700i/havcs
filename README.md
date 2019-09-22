自建技能配置参考旧插件

- 下载插件：[havcs][3]
- 前往[页面][4]注册账号，获取AppKey和AppSecret（生成后记得保存）
- 音箱APP->搜索'aihome'技能->关联账号->输入注册的账号信息登录
- 配置Home Assistant
  ```yaml
  # {HA配置目录}/configuration.yaml                 
  havcs:
    platform:                               # 音箱平台服务网关，至少启用一个
      - aligenie                            # 天猫精灵
      - dueros                              # 小度
      - jdwhale                             # 叮咚
    skill:
      bind_device: True                     # 是否启动时更新设备绑定信息。不设置默认True（叮咚音箱才有效）
      sync_device: False                    # 是否主动上报设备状态。不设置默认False（小度音箱才有效）
    # mqtt相关设置，启用http代理服务及APP技能服务才生效
    setting:
      app_key: {{your_app_key}}             # 注册账号获取的AppKey
      app_secret: {{your_app_secret}}       # 注册账号获取的AppSecret
      entity_key: {{your_entity_key}}       # 加密entity_id的key，自定义16个字符
    device_config: {{full_path}}            # 设备配置文件路径（完整路径）。不设置默认{HA配置目录}/havcs.yaml
  ```
- 配置设备信息
  ```yaml
  # {HA配置目录}/havcs.yaml
  entity_id:
    属性1:
    属性2:
  ```
  属性名 | 描述 | 取值 | 样例 | 备注
  :-: | :-: | :-: | :-: | :-: 
  havcs_enable | 是否启用设备 | True, False | True |仅值为False禁用，不设置该属性也为启用
  havcs_device_name | 设备名称 | [天猫精灵限制][5] | 客厅灯 | 建议“房间”+“设备类型”可以兼容三个平台使用
  havcs_zone | 设备位置| [天猫精灵限制][6] | 客厅 | 仅天猫精灵使用，其它可不用指定
  havcs_device_type | 设备类型 | light, switch, sensor, input_boolean | light | 一般不用指定
  havcs_attributes | 属性 | ['temperature', 'brightness', 'humidity', 'pm25', 'co2', 'power_state'] | ['power_state'] | 一般不用指定
  havcs_actions | 支持操作 | ['turn_on', 'turn_off', 'timing_turn_on', 'timing_turn_off', 'query_temperature', 'query_humidity', 'increase_brightness', 'decrease_brightness'] | ['turn_on', 'turn_off'] | 一般不用指定
  havcs_related_sensors | 传感器设备专用，关联真实传感器 | sensor/group列表 | ['sensor.demo', 'group.demo'] | 支持设置group，会搜索加入该分组下的sensor
- 更新音箱平台设备信息
  - 先重载本地信息：调用服务（HA web->开发者工具->服务->调用havcs.reload）或者重启HA
  - 叮咚：重载本地信息会触发上报（bind_device配置为True）。
  - 天猫精灵：在APP中重新绑定触发更新。
  - 小度：执行“发现设备”指令触发更新。