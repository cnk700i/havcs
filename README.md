# 备注
插件使用有点复杂，有疑问请加QQ群307773400交流。

# 更新日志
- 2019-02-27
  1. input_boolean支持直接调用service指令
- 2019-02-22
  1. 增加叮咚设备更新（插件启动触发更新）
  2. 修复京东音箱、小度音箱对input_boolean类的开/关控制
  3. 天猫精灵设备配置命名风格统一
  4. 更改设备发现模式为非主动发现,使用"aihome_device"属性设置设备可被发现
  5. 传感器类设备配置属性精简
  6. 说明文档补充设备配置样例
- 2019-01-xx
  HA 0.86.4 和 HA 0.82.1，本地单机测试。

# 插件说明
对目前智能音箱接入插件进行了整合，其中天猫精灵和小度音箱插件基于瀚思彼岸论坛[@feversky](https://bbs.hassbian.com/thread-4758-1-1.html)和[@zhkufish](https://bbs.hassbian.com/thread-5417-1-1.html)插件进行小修改，叮咚音箱插件参考前两个插件编写。
本插件有三种使用模式：

1. http网关，适合有公网ip自建测试技能接入
> 传统接入方法

2. http网关+mqtt中转，适合有无公网ip自建测试技能接入
> 原先本人[http2mqtt2hass](https://github.com/cnk700i/http2mqtt2hass)插件接入方法

3. mqtt，技能接入，目前技能暂未上线
> 原先计划采用自[定义技能方式接入](https://ljr.im/2019/01/20/aihomesmart-speaker-universal-access-platform/)，因翻车改用智能家居技能对接
# 配置说明（configuration.yaml）
```yaml
#{HA配置目录}/configuration.yaml
aihome:
  platform:                         # 加载内置智能音箱插件服务
    # - aligenie                        # 天猫精灵
    # - dueros                          # 小度
    - jdwhale                         # 叮咚
  http:                             # 启用http网关功能（模式一、模式二需设置）
    expire_in_hours: 24               # token超时时间，单位小时，不设置则默认24h
  mqtt:                             # 启用mqtt对接功能（模式二、模式三需设置）
    broker: mqtt.ljr.im               # MQTT服务器域名，不设置则默认为mqtt.ljr.im
    port: 28883                       # MQTT服务器端口，不设置则默认为28883
    app_key: xxx                      # 必填，https://ai-home.ljr.im/account/获取
    app_secret: xxx                   # 必填，https://ai-home.ljr.im/account/获取
    entity_key: xxx                   # 必填，加密entity_id的key，自由设置16位字符串
    certificate: xxx/ca.crt           # 必填，插件内ca.crt文件完整路径
    tls_insecure: true                # 必填，不校验证书主机名，因为ca.crt是自签证书，设置true
    ha_url: https://localhost:8123    # 本地HA访问网址，不设置则默认为http://localhost:8123
    allowed_uri:                      # http请求白名单，不设置则默认不限制（模式一、模式二才有效）
      - /auth/token
      - /dueros_gate
      - /aligenie_gate
      - /jdwhale_gate
     
```
# 设备配置
用于生成音箱云平台的设备信息。
- 整体配置框架
  ```yaml
  # 方法1 分散文件配置
  #{HA配置目录}/customize.yaml，用于生成音箱平台设备
  light.demo:
    属性1:
    属性2:
  sensor.livingroom:
    属性1:
    属性2:
  #{HA配置目录}/group.yaml，用于传感器类状态查询
  livingroom_sensors:
    view: no
    name: '客厅传感器列表'
    control: hidden
    entities: # 真实传感器列表
      - sensor.temperature
      - sensor.humidity
  #{HA配置目录}/configuration.yaml，用于传感器类状态查询
  sensor:
  - platform: template
    sensors:
      livingroom: # 虚拟传感器设备，整合多个真实传感器
        value_template: "客厅环境"
  ```
  ```yaml
  # 方法2 统一文件配置（建议方法）
  #{HA配置目录}/configuration.yaml
  homeassistant:
    packages: !include_dir_named packages
  #{HA配置目录}/packages/自定义名称.yaml
  homeassistant: # 用于生成音箱平台设备
    customize:
      light.demo:
        属性1:
        属性2:
      sensor.livingroom:
        属性1:
        属性2:
  group: # 用于传感器类状态查询
    livingroom_sensors:
      view: no
      name: '客厅传感器列表'
      control: hidden
      entities:  # 关联真实传感器列表
        - sensor.temperature
        - sensor.humidity
  sensor: # 用于传感器类状态查询
  - platform: template
    sensors:
      livingroom: # 虚拟传感器设备，整合多个真实传感器
        value_template: "客厅环境"
  ```
- 设备具体属性
  
  使用customize组件（{HA配置目录}/customize.yaml中配置）为HA的设备增加相关属性，音箱插件根据所配置生成对应音箱平台设备。
  ```yaml
  ---通用---
  # 上报设备数据
  aihome_device: True
  ```
  ```yaml
  ---传感器专用---
  # 虚拟传感器，关联真实传感器分组，详细用法见传感器类设备配置说明
  aihome_sensor_group: group.livingroom_sensors
  # 真实传感器，上报设备数据，详细用法见传感器类设备配置说明
  aihome_sensor: True
  ```
  ```yaml
  ---叮咚音箱---
  # 设备类型，不设置则尝试自动生成
  jdwhale_deviceType: 'LIGHT'
  # 设备支持操作，不设置则尝试自动生成
  jdwhale_actions: ['TurnOn', 'TurnOff', 'Query']
  ```
  ```yaml
  ---天猫精灵---
  # 设备别名（设备类型限定设备别名可取值）
  aligenie_deviceName: 灯
  # 设备类型，不设置则尝试自动生成
  aligenie_deviceType: 'light'
  # 设备位置，不设置则尝试自动生成
  aligenie_zone: 主卧
  ```
  ```yaml
  ---小度音箱---
  # 设备类型，不设置则尝试自动生成
  dueros_deviceType: 'LIGHT'
  # 设备支持操作，不设置则尝试自动生成
  dueros_actions: ['turnOn', 'turnOff']
  ```
  > __INFO：音箱的设备类型、支持的操作建议去官网看文档，无法一一详述。__
- 传感器类设备配置说明
  1. 环境类传感器先集中到一个分组
  ```yaml
  #{HA配置目录}/group.yaml，用于传感器类状态查询
  livingroom_sensors:
    view: no
    name: '客厅传感器列表'
    control: hidden
    entities: # 真实传感器列表
      - sensor.temperature
      - sensor.humidity
  ```
  2. 新增一个虚拟的sensor（使用官方sensor组件template生成即可）
  ```yaml
  #{HA配置目录}/configuration.yaml，用于传感器类状态查询
  sensor:
  - platform: template
    sensors:
      livingroom: # 虚拟传感器设备，整合多个真实传感器
        value_template: "客厅环境"
  ```
  3. 自定义虚拟sensor的属性，关联传感器分组
  ```yaml
  #{HA配置目录}/customize.yaml，用于生成音箱平台设备
  sensor.livingroom:
    friendly_name: 客厅传感器
    aihome_sensor_group: group.livingroom_sensors
    aihome_jdwhale_actions: ['Query', 'QueryTemperature', 'QueryHumidity'] # 根据真实传感器及音箱平台支持的类型设置
  sensor.temperature:
    aihome_sensor: True     # 上报传感器数据
  sensor.humidity:
    aihome_sensor: True     # 上报传感器数据
  ```
  >__INFO：建议虚拟sensor的名称命名为“{房间名}传感器”，各个平台的识别执行成功率比较高。__
  
>__INFO：原天猫精灵插件根据zone组合传感器，原小度插件没有实现相应查询功能，于是对查询方法进行了统一。__

- 直接调service类设备配置说明
  1. 新增一个input_boolean
  ```yaml
  #{HA配置目录}/configuration.yaml
  input_boolean:
    call_service:
  ```
  2. 自定义虚拟input_boolean的属性，在aihome_actions属性中设置对应的service指令（只能设置turn_on/turn_off，对应打开/关闭命令）
  ```yaml
  #{HA配置目录}/customize.yaml
    input_boolean.call_service:  
      friendly_name: 定时充电
      aihome_device: True
      aligenie_deviceName: 开关
      aligenie_deviceType: switch
      aligenie_zone: 主卧
      dueros_deviceType: 'SWITCH'
      dueros_actions: ['turnOn', 'turnOff']
      jdwhale_deviceType: 'SWITCH'
      jdwhale_actions: ['TurnOn', 'TurnOff']
      aihome_actions:
          # service指令格式:[domain, service_name, service_data（json字符串）]，具体内容需参见相应组件的服务定义。
          turn_on: ['common_timer', 'set', '{"entity_id":"switch.demo","duration":"01:00:00","operation":"off"}'] # 打开命令
          turn_off: ['common_timer', 'cancel', '{"entity_id":"switch.demo"}'] # 关闭命令
  ```
  >__INFO：调自动化(automation.turn_on)、调脚本(scrpit.turn_on)、调红外指令(climate.xiaomi_miio_send_command)等会比较适合。__

  >__INFO：天猫精灵无法自定义名称，不太适合使用。__
