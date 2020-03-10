## 备注
测试版本，0.101.3、0.104.2初步测试
## 改动
### 新增集成管理方式
WEB->配置->集成->右下角加号进行新增配置（不用在configuration.yml配置）

### 设备属性
| 属性名 | 描述 | 取值 | 样例 | 备注 |
| :-: | :-: | :-: | :-: | :-: |
| visable | 设备可见性 | ['aligenie', 'dueros', 'jdwhale'] | ['aligenie', 'dueros'] | 设置该属性则设备只对指定平台可见；如不设置，对所有平台可见 |
| name | 设备名称 | [*天猫精灵限制][5] | 客厅灯 | 必填，建议“房间”+“设备类型”可以兼容三个平台使用 |
| zone | 设备位置| [*天猫精灵限制][6] | 客厅 | 天猫精灵必填，其它可不用指定 |
| type | 设备类型 | light /switch /sensor /input_boolean | light | 一般不用指定 |
| attributes | 属性 | ['temperature', 'brightness', 'humidity', 'pm25', 'co2', 'power_state'] | ['power_state'] | 一般不用指定 |
| actions | 支持操作 | ['turn_on', 'turn_off', 'timing_turn_on', 'timing_turn_off', 'query_temperature', 'query_humidity', 'increase_brightness', 'decrease_brightness'] | ['turn_on', 'turn_off'] | 一般不用指定 |
| entity_id | 关联真实设备 | - | ['light.demo', 'group.demo'] | group配合type使用，会搜索加入该分组下的匹配的entity |