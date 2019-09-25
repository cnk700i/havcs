## 备注
- 插件名称更改为havcs，采用独立文件配置设备信息，不用再重启HA生效。
- 旧插件（aihome）到[release][1]页面下载。

# 更新日志
- 2019-09-25
  1. 重构音箱网关代码，改用独立文件配置设备信息
  2. 修复取消配置后不能正常清除config entry信息的问题
  3. 调整设备信息属性havcs_enable为havcs_visable，可以设置该设备只对指定平台可见
- 2019-09-17
  1. 修复天猫精灵获取变量信息失败导致初始化失败
- 2019-08-23
  1. HA 0.97.2版本下测试，修复一些小度音箱定时控制指令功能的bug
- 2019-08-20
  1. 小度音箱支持light、switch、inputboolean类型定时打开/关闭指令，需配合common_timer插件使用
- 2019-05-10
  1. 采用新方案，在不影响HA的token超时时间参数情况下，现在可以为token独立设置超时时间
- 2019-05-07
  1. 修复原生input_boolean打开关闭指令失效
  2. 修复token正则匹配不正确
- 2019-05-06
  1. 重新设计配置项更容易设置
  2. 优化三种模式代码逻辑
  3. 整合模式一服务网关，重新测试
  4. 优化调试日志的样式
- 2019-05-03
  1. input_boolean实体支持对调节亮度操作指令映射service（aihome_actions属性）
  2. 指令映射模式下，支持执行多条指令（设置方法有变化，请查看教程）
  2. HA 0.92.1版本测试
- 2019-04-09
  1. 增加设备配置样例（使用packages方式导入即可测试）
  2. 修复叮咚启动不同步信息bug
- 2019-04-07
  1. 精简配置项，增加模式三简略配置说明
- 2019-04-01
  1. 增加首次启动连接mqtt测试功能，如果正常INFO级别日志会显示提示信息，否则请检查appkey以及网络连接
- 2019-03-29
  1. 设备开关状态主动上报（小度音箱），可通过配置文件设置是否上报
  2. HA 0.90.2版本测试
  3. 前端页面优化，上线了密码找回功能
- 2019-03-06
  1. HA 0.88.2版本测试
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
  HA 0.86.4 和 HA 0.82.1，本地单机测试

## 使用说明
以APP的技能使用为例
- 下载havcs插件，放置到HA自定义插件目录，最终路径结构为`{HA配置目录}/custom_components/havcs/__init__.py`
- 前往[页面][4]注册账号，获取AppKey和AppSecret（先登录再生成，生成后记得保存）
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
  havcs_visable | 设备可见性 | ['aligenie', 'dueros', 'jdwhale'] | ['aligenie', 'dueros'] | 设置该设备只对指定平台可见，如不设置，对所有平台可见
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

## 调试
根据[教程][7]查看插件运行日志

[1]: https://github.com/cnk700i/havcs/releases "历史版本"
[4]: https://ai-home.ljr.im/account/ "智能音箱接入Home Assistant方案"
[5]: https://open.bot.tmall.com/oauth/api/aliaslist "天猫精灵设备名称"
[6]: https://open.bot.tmall.com/oauth/api/placelist "天猫精灵位置"
[7]: https://ljr.im/articles/home-assistant-novice-question-set/#3-%E8%B0%83%E8%AF%95%E5%8F%8A%E6%9F%A5%E7%9C%8B%E7%A8%8B%E5%BA%8F%E8%BF%90%E8%A1%8C%E6%97%A5%E5%BF%97 "调试及查看程序运行日志"
