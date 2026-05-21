# 开发路线图

基于文档(§1-22)与当前引擎实现的差距制定。完成任务后勾选 `[x]`。

---

## ✅ 已完成

- [x] 行动条/回合系统 (§5): SPD / AV / AG 公式 / 拉条推条 / 额外回合 / 终结技插队
- [x] 同 AV 平手规则 LIFO (§17.4 / §18.3): `_av_zero_ts` 计数器, `min()` key = `(av, -ts)`
- [x] 基础伤害系统 (§7-8): 七乘区框架 / DEF / RES / Weaken / BreakDamageIncrease / SuperBreak
- [x] 弱点击破系统 (§10): 削韧 / 击破伤害 / 击破异常 / Broken 恢复 / ToughnessDamagePacket / 削韧效率
- [x] 状态机 (§12): 修饰器池 / duration 递减 / dispellable / tickTiming / 驱散净化 / 角色 CC
- [x] 叠层策略: apply_modifier() 6 种策略 (refresh/independent/add_stacks/replace_weaker/replace_stronger/no_stack)
- [x] 资源系统 (§4-5): SP / Energy / 秘技 / 伏击 / 波次 / WaveStart
- [x] 受击回能分段 (§17.2): `BaseEnemy.hit_energy_bucket` 字段
- [x] FUA 返能分类 (§17.2): `follow_up_energy_type` + `FOLLOW_UP_ENERGY` 配置
- [x] 事件系统 (§13-14): EventBus(30事件) / FUA 队列 / Extra Turn 队列 / 攻击标签 / 多段 Hit / ON_SHIELD_APPLIED / ON_STATUS_APPLY
- [x] 目标选择 (§11): Aggro 仇恨 / Bounce / Blast / AoE / Random / LockOn > Taunt
- [x] 欢愉体系 (§13.0): ELATION 乘区链 / Aha 倒计时 / Punchline / CertifiedBanger / Aha Instant
- [x] 三月七天赋反击: ON_HIT 监听器 → 护盾检查 → FUA 反击
- [x] 生存系统 (§9): 护盾吸收下沉至 take_damage / ShieldStatus.duration / BEFORE_DEATH/UNIT_DOWNED/HEAL_DONE
- [x] 配置化(§17): SP/Energy/Aggro/Cycle/Ambush/FollowUpEnergy 提取至 config/game_config.py
- [x] 模块拆分: core/toughness.py (击破+CC) / config/ 目录 / core/damage/ 子包
- [x] 三月七完整重构: 对标 JSON 数据实现普攻/战技(护盾+嘲讽600%)/终结技(群攻+冻结DoT)/天赋(反击+E4DEF增伤)/秘技 + 行迹(纯洁/加护/冰咒) + 星魂(E1~E6)
- [x] 元素专属增伤体系: 7种 StatType + get_element_dmg_bonus + 通用与元素加法叠加
- [x] 外部嘲讽因子: Fighter.external_taunt_factor + 战技600% + 护盾消失重置
- [x] 冻结附加伤害: FreezeDotStatus + ADDITIONAL_DMG 独立乘区链 + TURN_START 结算
- [x] 净化系统: dispel_one (CC > debuff modifier > DoT 优先级)
- [x] 角色实现: DanHeng (巡猎·风) — 减速/条件增伤/RES_PEN/拉条E4
- [x] 角色实现: March7th (存护·冰) — 护盾/嘲讽/冻结DoT/反击
- [x] 角色实现: PlayerGirl (毁灭·物理) — 扩散/终结技二选一/击破叠层
- [x] 角色实现: Himeko (智识·火) — 充能FUA/灼烧DoT/条件暴击
- [x] 角色实现: Welt (虚无·虚数) — 弹射/禁锢/失重debuff/EHR→ATK转换
- [x] 角色实现: Kafka (虚无·雷) — DoT引爆/触电Shock/天赋FUA计数
- [x] 角色实现: SilverWolf (虚无·量子) — 弱点植入/全属性抗性降低/缺陷/减防/EHR→ATK转换
- [x] 角色实现: Arlan (毁灭·雷) — HP消耗不耗SP/多段攻击/HP→DMG天赋/免死E4/免疫A3
- [x] 弹射系统: TargetManager.select_target(is_bounce=True)
- [x] 失重系统: enemy.weightless 字段 + ON_DAMAGE_DEALT 延迟 + 命中计数
- [x] DoT 引爆: _detonate_dots() 通用函数
- [x] 条件属性转换: A6 Verdict (EHR→ATK) / A2 Torture (队友 EHR→ATK)
- [x] 测试体系: 312 tests (36 角色专属 + 5 集成 + 6 边缘)
- [x] 文档完善: character_implementation_guide.md v2 (增强版技能/新机制速查/测试指南)

---

## ❌ 确定缺失的引擎机制

### 弱点植入系统 (Silver Wolf)
- [x] 弱点植入: `ImplantedWeakness` dataclass + `enemy.implanted_weakness` 字段
- [x] Per-element RES 修改: `enemy.element_res_modifiers: dict[ElementType, float]`
- [x] `resistance_multiplier` 支持植入弱点 + per-element RES
- [x] Per-element 易伤体系: 7种 StatType (FIRE_VULN ~ IMAGINARY_VULN) + `_ELEMENT_VULN_MAP`
- [x] Himeko 秘技修正: `VULNERABILITY` → `FIRE_VULN` (火属性伤害易伤)
- [x] `apply_vulnerability` / `apply_elation_vuln` 支持元素参数

### 遗器套装效果激活 (§12 / §16)

- 当前: `RelicSetManager.check_and_apply_set_effects` 方法存在，但无套装效果实现
- 缺失: 具体遗器套装的 buff/debuff 逻辑（如快枪手、铁卫等）

### 光锥被动效果

- [x] 光锥注册表 + `on_combat_start` 引擎接入 + `_decrement_modifiers(unit)` 修复
- [x] `superimpose` 叠影字段 + 光锥数据提取 (161 LCs)
- [x] 锋镝(20000) 端到端 Pipeline: `Arrows` + `ArrowsEffect` + 12 测试
- [x] 命途限制校验: `lc.path != char.path` 时跳过特效激活，基础面板仍生效
- [x] Pipeline 指引文档 `docs/light_cone_pipeline.md`
- [x] 光锥等级系统: `_PROMOTIONS` 分段线性插值, Lv1-80 整数级精确
- [x] 一场术后对话(21000/4★/丰饶): ERR 永久 + 终结技治疗加成 (ON_ULTIMATE_INSERTED)
- [x] 银河铁道之夜(23000/5★/智识): 敌人计数 ATK 叠加 + 弱点击破 DMG (UNIT_DOWNED + ON_WEAKNESS_BREAK)
- [ ] 更多光锥特效实现

### 敌人多技能/行动模式 (§16)

- 当前: 敌方仅 `attack()` 单一行动
- 缺失: 技能列表 + 条件选择 (HP阈值/冷却/随机) + 多阶段行为

### 召唤物扩展字段 (§13.3)

- 当前: Memosprite 基础骨架 (HP/SPD/ATK 继承)
- 缺失: `durationMode` (indefinite/turn_count/action_count/special) / `remainingActions`
- 需实现: Memosprite 生命周期管理 (限时/限次召唤物)

### DoT 专属增伤 StatType

- 当前: 用 `DMG_BONUS` 通用增伤近似 DoT 增伤 (Kafka E2)
- 缺少: 类似 `DOT_DMG` 的专属 StatType，否则 E2 会错误影响非 DoT 伤害

---

## ⚠️ 待社区实测确认的配置项 (§17)

| 项 | 当前假设 | 风险 |
|---|---|---|
| SP carryOverBetweenWaves | `True` (config) | 待录像验证 |
| LockOn vs Taunt 优先级 | LockOn > Taunt | 文档 §11.5 说未锁定 |
| 多段攻击返能时点 | 首段后跳过 | 待补实测 |
| beingHitBucket 具体分段 | 固定 10 | 敌攻击模板未定义 |
| 换波 AV 重置规则 | per-entity 标记 | 文档 §3 说应脚本化 |

---

## 架构改进记录

- [x] 欢愉伤害子系统: 独立 DamageType + 乘区链 + Elation LM 表 + Punchline/CertifiedBanger
- [x] Aha 倒计时对象: countdown_units 框架 + CombatEngine 调度 + Aha Instant 结算窗口
- [x] BREAK / SUPER_BREAK 乘区链移除 weaken (§8.5/§8.8 对齐)
- [x] 护盾吸收下沉至 `Fighter.take_damage()`: 顺序吸收 + `bypass_shield` 参数
- [x] 死亡事件: `BEFORE_DEATH` / `UNIT_DOWNED` + `_notify_death` 统一 emit
- [x] `ShieldStatus.duration` 字段 + 递减
- [x] `HEAL_DONE` 事件
- [x] 事件枚举 30 类型 + 26 个 emit 点
- [x] 目标选择: Blast / AoE / Random / Bounce
- [x] 配置文件化: `config/game_config.py` (SP/Energy/Aggro/Cycle/Ambush/FollowUpEnergy)
- [x] 模块拆分: `core/toughness.py` (击破+CC) / `config/` 目录
- [x] 波次系统 + 秘技接口 + 伏击
- [x] 三月七天赋反击 (事件驱动 → ON_HIT 监听)
- [x] 多段 Hit: `HitPacket` + `execute_multi_hit` + `skip_action_resources`
- [x] 同 AV 平手 LIFO: `_av_zero_ts` 计数器
- [x] `BaseEnemy.hit_energy_bucket` + `FOLLOW_UP_ENERGY` FUA 返能分类
- [x] `apply_modifier()` 叠层策略 6 种
- [x] `Fighter.apply_shield()` + ON_SHIELD_APPLIED / ON_STATUS_APPLY emit
- [x] Enhanced 技能版本体系: 11004xx ID 前缀识别 (Welt / Kafka)
- [x] DoT 引爆通用函数: `_detonate_dots(state, target, pct)`
- [x] 失重系统: enemy.weightless 字段 + 命中计数 + 延迟 + 到期清理
- [x] 条件属性转换: EHR→ATK (Welt A6) / 队友 EHR→ATK (Kafka A2)
- [x] `__init__` flags 初始化顺序修正: 必须在 `super().__init__()` 之前
- [x] 文档完善: character_implementation_guide.md v2
- [x] 弱点植入系统: `ImplantedWeakness` + per-element RES + resistance_multiplier 扩展
- [x] SilverWolf 完整实现: 5技能 + 10 stat traces + 3 ability traces + E1~E6
- [x] 角色级削韧/回能覆盖: `BaseCharacter._toughness_map` / `_energy_map` → fallback 全局 config
- [x] `Fighter._nullify_direct_dmg` 字段: 非DoT伤害免疫直到首次受击 (Arlan A3)
- [x] Arlan 完整实现: 5技能(多段普攻30/70, HP战技不耗SP, 多段扩散终结技30/10/60, HP→DMG天赋) + E1~E6
- [x] 全局默认削韧调整: ULTIMATE 30→20, 新增 FOLLOW_UP=10
- [x] FUA 回能调整: type2 5→10 (统一到10)
- [x] 全部8角色 _toughness_map / _energy_map 补全: DanHeng ULT=30, PlayerGirl 能量特化, 其余角色用新全局默认
- [x] 扩散技能削韧: PlayerGirl/Himeko/Kafka 战技主20邻10
- [x] FUA 削韧 packet: Himeko/Kafka/March7th FUA=10
- [x] Welt 弹射技能削韧: 每段10 + skip_action_resources
- [x] March7th 秘技修复: 添加缺失的AoE伤害+削韧20
- [x] SilverWolf 秘技削韧: 60→10
- [x] 角色实现: Asta (同谐·火) — 弹射战技/全体SPD buff/蓄能ATK天赋/灼烧/火伤光环/DEF叠层
- [x] 角色实现: Herta (智识·冰) — 2段AoE战技/HP条件增伤/冻结终结技增伤/HP阈值天赋FUA/波次清理/多段Hit
