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
- [x] 测试体系: 761 tests across 12 files (test/)
- [x] 文档完善: character_implementation_guide.md v2 (增强版技能/新机制速查/测试指南)
- [x] 位面饰品基础设施: entities/planar_ornaments/ 目录 + base.py 共享基类 (BaseRelic/RelicSetEffect)
- [x] 位面饰品实现: 301 太空封印站 (ATK% + SPD≥120 条件ATK%)
- [x] 位面饰品实现: 302 不老者的仙舟 (HP% + 全队ATK%可叠加)
- [x] 位面饰品实现: 303 泛银河商业公司 (EHR% + EHR→ATK动态换算)
- [x] 位面饰品实现: 304 筑城者的贝洛伯格 (DEF% + EHR≥50%条件DEF%)
- [x] 位面饰品实现: 305 星体差分机 (CRIT_DMG% + 首击前CRIT_RATE+60%)
- [x] 位面饰品实现: 306 停转的萨尔索图 (CRIT_RATE% + 条件ULT/FUA_DMG%)
- [x] 位面饰品实现: 308 生命的翁瓦克 (ERR% + BATTLE_START拉条40%)

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

- [x] 11 个隧洞遗器套装实现 (101-111): 含事件订阅 / 叠层 / 条件触发
- [x] 位面饰品基础设施: entities/planar_ornaments/ 目录 + 301 太空封印站
- [ ] 其余位面饰品实现 (302-326): 待按模板批量添加

### 光锥被动效果

- [x] 光锥注册表 + `on_combat_start` 引擎接入 + `_decrement_modifiers(unit)` 修复
- [x] `superimpose` 叠影字段 + 光锥数据提取 (161 LCs)
- [x] 锋镝(20000) 端到端 Pipeline: `Arrows` + `ArrowsEffect` + 12 测试
- [x] 命途限制校验: `lc.path != char.path` 时跳过特效激活，基础面板仍生效
- [x] Pipeline 指引文档 `docs/light_cone_pipeline.md`
- [x] 光锥等级系统: `_PROMOTIONS` 分段线性插值, Lv1-80 整数级精确
- [x] 一场术后对话(21000/4★/丰饶): ERR 永久 + 终结技治疗加成 (ON_ULTIMATE_INSERTED)
- [x] 银河铁道之夜(23000/5★/智识): 敌人计数 ATK 叠加 + 弱点击破 DMG (UNIT_DOWNED + ON_WEAKNESS_BREAK)
- [x] **3★ 光锥全补齐 (14 个):**
  - [x] 离弦(20007/巡猎): ON_KILL → ATK% up 3T
  - [x] 相抗(20014/巡猎): ON_KILL → SPD% up 2T
  - [x] 睿见(20020/智识): ON_ULTIMATE_INSERTED → ATK% up 2T
  - [x] 戍御(20010/存护): ON_ULTIMATE_INSERTED → heal maxHP%
  - [x] 开疆(20017/存护): ON_WEAKNESS_BREAK → heal maxHP%
  - [x] 嘉果(20008/丰饶): BATTLE_START → team energy
  - [x] 调和(20019/同谐): BATTLE_START → team SPD flat 1T
  - [x] 俱殁(20016/毁灭): HP<80% → CRIT_RATE% (HP threshold toggle)
  - [x] 蕃息(20015/丰饶): AFTER_ACTION(BA) → advance_action%
  - [x] 乐圮(20009/毁灭): ACTION_START HP>50% → DMG_BONUS% (per-target conditional)
  - [x] 渊环(20011/虚无): ACTION_START target slowed → DMG_BONUS% (per-target conditional)
  - [x] 轮契(20012/同谐): ON_DAMAGE_DEALT/ON_HIT → energy (1/turn gate)
  - [x] 灵钥(20013/智识): AFTER_ACTION(SKILL) → energy (1/turn gate)
- [x] 匿影(20018/虚无): AFTER_ACTION(SKILL) → next BA ADDITIONAL_DMG instance
- [x] **引擎基础设施 (2 项):**
  - [x] `count_debuffs()` 统一函数: `entities/base.py` — 统计 value<0 mods + CC + DoT
  - [x] `StatType.DOT_DMG` 新增 + `core/damage/multipliers.py` DoT乘区链接入
- [x] **4★ 光锥 (8 个):**
  - [x] 舞！舞！舞！(21018/同谐): ON_ULTIMATE → team advance_action%
  - [x] 余生的第一天(21002/存护): 永久DEF% + BATTLE_START team RES%
  - [x] 猎物的视线(21008/虚无): 永久EHR% + 永久DOT_DMG%
  - [x] 天才们的休憩(21020/智识): 永久ATK% + ON_KILL CRIT_DMG 3T
  - [x] 秘密誓心(21012/毁灭): 永久DMG% + per-target HP比较条件增伤
  - [x] 延长记号(21022/虚无): 永久BREAK_EFFECT% + per-target Shock/WindShear条件增伤
  - [x] 镂月裁云之意(21032/同谐): BATTLE/TURN_START random team buff (3选1,防重复)
  - [x] 晚安与睡颜(21001/虚无): per-target debuff计数→DMG% (max 3层)
- [x] **引擎基础设施 追加 (2 项):**
  - [x] `dispel_one_buff()`: `core/game_state.py` — 驱散敌方正面增益
  - [x] `StatModifier.tag` 字段: `entities/base.py` — Resolution Shines 标记"攻陷"状态
- [x] **4★ 光锥 (12 个):**
  - [x] 朗道的选择(21009/存护): 永久AGGRO_MODIFIER + DMG_MITIGATION
  - [x] 无处可逃(21033/毁灭): 永久ATK% + ON_KILL 回血
  - [x] 唯有沉默(21003/巡猎): 永久ATK% + ≤2敌→CRIT_RATE (enemy计数)
  - [x] 别让世界静下来(21013/智识): BATTLE_START回能 + 永久ULT_DMG%
  - [x] 记忆中的模样(21004/同谐): 永久BREAK_EFFECT% + 攻击回能(1次/回合)
  - [x] 与行星相会(21011/同谐): team DMG_BONUS(匹配元素时) — ACTION_START/AFTER_ACTION
  - [x] 等价交换(21021/丰饶): TURN_START→随机低能量队友→gain_energy
  - [x] 重返幽冥(21031/巡猎): 永久CRIT_RATE + 暴击固定概率驱散增益
  - [x] 过往未来(21025/同谐): 战技后→下一行动队友 DMG_BONUS 1T
  - [x] 春水初生(21024/巡猎): 状态机 ACTIVE↔BROKEN↔RESTORE(SPD%+DMG%)
  - [x] 此时恰好(21014/丰饶): 永久EFF_RES + 动态衰减转换→OUTGOING_HEALING_BOOST
  - [x] 决心如汗珠般闪耀(21015/虚无): 基础概率命中→【攻陷】DEF-12~16% 1T
- [x] **引擎基础设施 追加 (1 项):**
  - [x] `_extra_base_dmg` 支持: `core/damage/base.py` — This Is Me! 的 DEF→基础伤害 flat bonus
- [x] **4★ 光锥 (14 个):**
  - [x] 同一种心情(21007/丰饶): 永久HEAL_BOOST + 战技后 team回能
  - [x] 早餐的仪式感(21027/智识): 永久DMG_BONUS + ON_KILL ATK叠层
  - [x] 在蓝天下(21019/毁灭): 永久ATK + ON_KILL CRIT_RATE 3T
  - [x] 暖夜不会漫长(21028/丰饶): 永久HP + BA/SKILL后 team heal
  - [x] 汪！散步时间！(21026/毁灭): 永久ATK + per-target Burn/Bleed条件DMG
  - [x] 「我」的诞生(21006/智识): 永久FUA_DMG + HP≤50%额外FUA_DMG
  - [x] 点个关注吧！(21017/巡猎): 永久BAS/SKILL_DMG + 满能量额外DMG
  - [x] 我们是地火(21023/存护): BATTLE_START team DMG_MITIGATION 5T + 回血
  - [x] 鼹鼠党欢迎你(21005/毁灭): BA/Skill/Ult各1层【淘气值→ATK%】
  - [x] 后会有期(21029/虚无): BA/Skill后→随机受击目标ADDITIONAL_DMG
  - [x] 今日亦是和平一日(21034/智识): DMG_BONUS = min(energy,160) × per_energy
  - [x] 宇宙市场趋势(21016/存护): 永久DEF + 受击→基础概率灼烧DoT(DEF×coeff)
  - [x] 论剑(21010/巡猎): per-hit叠层(同目标),目标变化重置
  - [x] 这就是我啦！(21030/存护): 永久DEF + 终结技 DEF→base_dmg 附加

---

## ⚠️ 待社区实测确认的配置项 (§17)

| 项 | 当前假设 | 风险 |
|---|---|---|
| SP carryOverBetweenWaves | `True` (config) | 待录像验证 |
| LockOn vs Taunt 优先级 | LockOn > Taunt | 文档 §11.5 说未锁定 |
| 多段攻击返能时点 | 首段后跳过 | 待补实测 |
| beingHitBucket 具体分段 | 固定 10 | 敌攻击模板未定义 |
| 换波 AV 重置规则 | per-entity 标记 | 文档 §3 说应脚本化 |


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
- [x] **代码债清理 (2026-05-22):** ElementType 重复定义修复 (元素增伤静默失效 bug)
- [x] 事件订阅泄漏修复: `EventBus.clear_all()` + `BATTLE_END` 清理
- [x] `_killing_action` 字符串标志反模式消除: → 事件 `action_type` kwargs (11 文件)
- [x] SPD 重算重复代码提取: `_recalc_spd_if_changed()` 公共方法
- [x] action_name 解析重复代码提取: `_ACTION_NAMES` 模块级 dict
- [x] Himeko ON_WEAKNESS_BREAK `breaker→source` key 名不匹配修复
- [x] `from __future__ import annotations` 补全至全部 84 个 .py 文件
- [x] 测试文件拆分: `test_starrail_combat.py` (5933行) → `test/` 目录 11 个按模块的文件 (402 tests)
- [x] Light Cone 语义修复 (2026-05-27):
  - [x] `only_silence_remains.py`: 拆分 ATK/CRIT source 串，防止互相覆盖
  - [x] `collateral.py`: 加身份校验，仅装备者施放技能触发治疗提升
  - [x] `return_to_darkness.py`: per-action 触发解增益（原 per-hit 多段多判）
  - [x] `subscribe_for_more.py`: 满能量额外增伤限定普攻和战技（原误用全局 DMG_BONUS）
  - [x] `resolution_shines.py`: 攻陷 debuff 刷新持续时间（原命中已有目标跳过）
  - [x] `but_battle_isnt_over.py`: 用 `state.characters` 替代 `hasattr(dot_statuses)` 判断友方
  - [x] `amber.py`: 开局 BATTLE_START 时检查 HP，触发条件额外 DEF
  - [x] `river_flows_in_spring.py`: 受击后首次 TURN_END 标记、二次 TURN_END 恢复（原当回合即恢复）
  - [x] `planetary_rendezvous.py`: 改为 BATTLE_START 常驻光环 + 死亡移除/复活恢复（原 ACTION_START/AFTER_ACTION 成对模式）
  - [x] `known_issues.md`: 创建文档，记录条件增伤模式局限、count_debuffs 语义、乘区验证等
