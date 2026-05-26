from __future__ import annotations
"""GameState — 战技点管理、终极技队列、伤害结算、胜负判定。"""

from typing import Optional

from core.damage import MULTIPLIER_CHAIN
from core.damage.base import compute_base_damage
from core.enums import ActionType, DamageType, DEBUFF_RES_MAP, ElementType, StatType
from core.events import EventType
from entities.base import ToughnessDamagePacket, HitPacket
from config.game_config import TOUGHNESS_DAMAGE, ENERGY_REGEN, ENERGY_ON_KILL, ENERGY_ON_HIT, SP_INITIAL, SP_MAX, SP_MIN, FOLLOW_UP_ENERGY


class GameState:
    """管理战技点、终结技待发队列、队伍阵容、胜负判定。"""

    def __init__(self, characters: list["Character"], enemies: list["Enemy"]) -> None:
        self.characters = characters
        self.enemies = enemies
        self.max_sp: int = SP_MAX
        self.min_sp: int = SP_MIN
        self.skill_points: int = SP_INITIAL
        self.ultimate_pending: list["Character"] = []
        self.follow_up_action_pending: list[tuple["Character", "object", bool]] = []
        self.extra_turn_pending: list[tuple["Character", "object"]] = []
        # 连携攻击注册表: 主攻击者 → [连携角色]
        self.joint_attack_registry: dict[str, list["Character"]] = {}
        self.event_bus: "EventBus | None" = None
        self.punchline: int = 0
        self.countdown_units: list["Fighter"] = []
        # 波次系统
        self.waves: list[list["Enemy"]] = [list(enemies)]  # 当前wave=0
        self.current_wave: int = 0
        self.technique_effects: list = []  # Callable[[GameState], None]
        self.is_ambush: bool = False

    # --- 战技点操作 ---

    def consume_sp(self) -> bool:
        if self.skill_points > self.min_sp:
            self.skill_points -= 1
            return True
        return False

    def generate_sp(self) -> None:
        if self.skill_points < self.max_sp:
            self.skill_points += 1

    # --- 终结技待发队列 ---

    def declare_ultimate(self, character: "Character") -> None:
        if character in self.ultimate_pending:
            return
        self.ultimate_pending.append(character)
        if self.event_bus is not None:
            self.event_bus.emit(EventType.ON_ULTIMATE_QUEUED, character=character)

    def has_pending_ultimates(self) -> bool:
        return len(self.ultimate_pending) > 0

    def pop_next_ultimate(self) -> Optional["Character"]:
        if self.ultimate_pending:
            return self.ultimate_pending.pop(0)
        return None

    # --- 追加行动队列 (Priority 1) ---

    def grant_follow_up_action(
        self, character: "Character", skill: object,
        is_follow_up_action: bool = True,
    ) -> None:
        """挂载追加行动至最高优先级队列 (攻击/治疗/状态切换等)。"""
        self.follow_up_action_pending.append((character, skill, is_follow_up_action))

    def has_follow_up_action(self) -> bool:
        return len(self.follow_up_action_pending) > 0

    def pop_next_follow_up_action(self) -> Optional[tuple["Character", "object", bool]]:
        if self.follow_up_action_pending:
            return self.follow_up_action_pending.pop(0)
        return None

    # --- 额外回合队列 (Priority 2) ---

    def grant_extra_turn(
        self, character: "Character", skill: object,
        is_turn_extension: bool = False,
    ) -> None:
        """挂载额外回合。is_turn_extension=True 时立即执行不走队列。"""
        if is_turn_extension:
            return  # 调用方即时处理
        self.extra_turn_pending.append((character, skill))

    def has_extra_turn(self) -> bool:
        return len(self.extra_turn_pending) > 0

    def pop_next_extra_turn(self) -> Optional[tuple["Character", "object"]]:
        if self.extra_turn_pending:
            return self.extra_turn_pending.pop(0)
        return None

    # --- 连携攻击 (Joint Attack) ---

    def register_joint_attacker(
        self, main_attacker_id: str, joint_character: "Character",
    ) -> None:
        """注册连携关系: joint_character 在 main_attacker_id 行动时连携。"""
        self.joint_attack_registry.setdefault(main_attacker_id, []).append(
            joint_character
        )

    def get_joint_attackers(self, main_character: "Character") -> list["Character"]:
        """获取某主攻击者的连携攻击者列表。"""
        return self.joint_attack_registry.get(main_character.name, [])

    # --- 伤害结算 (可插拔乘区链) ---

    def execute_action(
        self,
        character: "Character",
        action_type: ActionType,
        target: "Enemy",
        skill_multiplier: float,
        damage_type: DamageType = DamageType.DIRECT,
        base_damage_override: Optional[int] = None,
        element_override: Optional[ElementType] = None,
        break_effect_override: Optional[float] = None,
        tags: set[str] | None = None,
        toughness_packet: Optional[ToughnessDamagePacket] = None,
        skip_action_resources: bool = False,
        follow_up_energy_type: int = 1,
    ) -> tuple[int, bool, float, bool]:
        """执行角色动作：七乘区伤害、能量、战技点、韧性削韧。

        乘区链由 MULTIPLIER_CHAIN[damage_type] 控制顺序。
        """
        is_dot = damage_type == DamageType.DOT
        is_add = damage_type == DamageType.ADDITIONAL_DMG

        # ── 能量 / SP (DOT / ADD / skip 跳过) ──
        if not is_dot and not is_add and not skip_action_resources:
            if self.event_bus is not None:
                self.event_bus.emit(EventType.ON_BEFORE_PAY_COST, character=character,
                                     action_type=action_type)
            char_energy = getattr(character, "_energy_map", None) or {}
            regen = char_energy if char_energy else ENERGY_REGEN
            if action_type == ActionType.BASIC_ATTACK:
                character.gain_energy(regen.get(ActionType.BASIC_ATTACK, ENERGY_REGEN[ActionType.BASIC_ATTACK]))
                self.generate_sp()
            elif action_type == ActionType.ENHANCED_BASIC:
                character.gain_energy(regen.get(ActionType.ENHANCED_BASIC, ENERGY_REGEN.get(ActionType.ENHANCED_BASIC, 30.0)))
            elif action_type == ActionType.SKILL:
                character.gain_energy(regen.get(ActionType.SKILL, ENERGY_REGEN[ActionType.SKILL]))
                self.consume_sp()
            elif action_type == ActionType.ULTIMATE:
                character.set_energy(int(regen.get(ActionType.ULTIMATE, ENERGY_REGEN[ActionType.ULTIMATE])))
            elif action_type == ActionType.FOLLOW_UP:
                character.gain_energy(FOLLOW_UP_ENERGY.get(follow_up_energy_type, 0.0))
            else:
                character.gain_energy(regen.get(action_type, ENERGY_REGEN.get(action_type, 0.0)))

            if self.event_bus is not None:
                self.event_bus.emit(EventType.ON_AFTER_PAY_COST, character=character,
                                     action_type=action_type)

        # ── 基础伤害 ──
        final_damage = compute_base_damage(
            damage_type, character, skill_multiplier, base_damage_override,
        )

        # ── 遍历乘区链 ──
        chain = MULTIPLIER_CHAIN.get(damage_type, [])
        is_crit = False
        effective_element = element_override if element_override is not None else character.element
        for name, fn in chain:
            if name == "res":
                final_damage = fn(final_damage, character, target, element_override=element_override)
            elif name == "crit":
                final_damage, is_crit = fn(final_damage, character, target)
            elif name == "dmg_bonus":
                final_damage = fn(final_damage, character, target,
                                   action_type=action_type, damage_type=damage_type,
                                   tags=tags, element=effective_element)
            elif name == "break_effect":
                final_damage = fn(final_damage, character, target,
                                   break_effect_override=break_effect_override)
            elif name == "punchline":
                final_damage = fn(final_damage, character, target, state=self)
            elif name in ("vuln", "elation_vuln"):
                final_damage = fn(final_damage, character, target, element=effective_element)
            else:
                final_damage = fn(final_damage, character, target)

        # 事件: ON_DAMAGE_CALCULATED
        if self.event_bus is not None:
            self.event_bus.emit(EventType.ON_DAMAGE_CALCULATED, source=character,
                                 target=target, damage=final_damage,
                                 damage_type=damage_type)

        # ── 护盾吸收 + 扣血 (由 Fighter.take_damage 统一处理, DoT 走 bypass_shield) ──
        if self.event_bus is not None and not is_dot:
            self.event_bus.emit(EventType.ON_BEFORE_HIT, source=character,
                                 target=target, damage=final_damage,
                                 damage_type=damage_type)
        actual_damage = target.take_damage(final_damage, bypass_shield=is_dot, mitigated=True)
        if damage_type != DamageType.BREAK:
            target.hit_count += 1

        # 事件: ON_HIT
        if self.event_bus is not None:
            self.event_bus.emit(
                EventType.ON_HIT, source=character, target=target,
                damage=actual_damage, action_type=action_type,
                damage_type=damage_type, is_crit=is_crit,
            )
            self.event_bus.emit(
                EventType.ON_DAMAGE_DEALT, source=character, target=target,
                damage=actual_damage, damage_type=damage_type,
            )
            if not target.is_alive:
                self._notify_death(target, character)
                self.event_bus.emit(
                    EventType.ON_KILL, source=character, target=target,
                    action_type=action_type,
                )
                self.on_kill(character)

        # 纠缠叠层 (受击 +1, 上限 5)
        for cc in getattr(target, "cc_statuses", []):
            if cc.cc_type == "Entanglement" and cc.stacks < 5:
                cc.stacks += 1

        # 忆灵死亡自动解除
        if hasattr(target, "is_memosprite") and not target.is_alive:
            target.master.memosprite = None

        # ── 削韧判定 (DOT/屏障拦截 跳过) ──
        is_dot_or_add = is_dot or is_add
        toughness_dealt: float = 0.0
        did_weakness_break = False

        if not is_dot_or_add and damage_type != DamageType.BREAK:
            if toughness_packet is None:
                char_toughness = getattr(character, "_toughness_map", None) or {}
                base_amount = char_toughness.get(action_type) if char_toughness else None
                if base_amount is None:
                    base_amount = TOUGHNESS_DAMAGE.get(action_type, 0.0)
                toughness_packet = ToughnessDamagePacket(
                    amount=base_amount,
                    element=character.element,
                )

            if toughness_packet.amount > 0 and not target.broken:
                element_to_check = toughness_packet.element or character.element
                if element_to_check is not None:
                    if toughness_packet.ignores_weakness or element_to_check in target.weaknesses:
                        scaled = toughness_packet.amount * max(0.0, toughness_packet.efficiency_multiplier)
                        toughness_dealt = min(target.current_toughness, scaled)
                        target.current_toughness -= toughness_dealt
                        if toughness_dealt > 0 and self.event_bus is not None:
                            self.event_bus.emit(EventType.ON_TOUGHNESS_DAMAGE,
                                                 source=character, target=target,
                                                 amount=toughness_dealt,
                                                 element=element_to_check)
                        if target.current_toughness <= 0:
                            target.current_toughness = 0
                            target.broken = True
                            did_weakness_break = True
                            target.broken_by = element_to_check
                            target.broken_source_id = character.character_id
                            if self.event_bus is not None:
                                self.event_bus.emit(
                                    EventType.ON_WEAKNESS_BREAK, source=character, target=target,
                                    action_type=action_type,
                                )

        return (actual_damage, is_crit, toughness_dealt, did_weakness_break)

    # --- 多段攻击 ---

    def execute_multi_hit(
        self,
        character: "Character",
        hits: list["HitPacket"],
        action_type: ActionType = ActionType.BASIC_ATTACK,
        damage_type: DamageType = DamageType.DIRECT,
        tags: set[str] | None = None,
    ) -> list[tuple[int, bool, float, bool]]:
        """多段攻击: 逐段 execute_action, 首段扣资源, 后续段跳过。"""
        results: list[tuple[int, bool, float, bool]] = []
        for i, hit in enumerate(hits):
            if hit.target is None:
                continue
            skip = (i > 0)
            r = self.execute_action(
                character, action_type, hit.target, hit.skill_multiplier,
                damage_type=damage_type, element_override=hit.element_override,
                toughness_packet=hit.toughness_packet, tags=tags,
                skip_action_resources=skip,
            )
            results.append(r)
        return results

    # --- DoT 持续伤害 ---

    def resolve_enemy_dot_ticks(self, enemy: "Enemy") -> list[dict]:
        from entities.base import DoTStatus

        log: list[dict] = []
        remaining: list[DoTStatus] = []

        for dot in enemy.dot_statuses:
            source = dot.source_character
            if not source.is_alive:
                continue

            base_dmg = int(
                dot.dot_multiplier * dot.stacks
                if dot.is_break_induced
                else source.atk * dot.dot_multiplier * dot.stacks
            )
            damage, _, _, _ = self.execute_action(
                character=source,
                action_type=ActionType.BASIC_ATTACK,
                target=enemy,
                skill_multiplier=0.0,
                damage_type=DamageType.DOT,
                base_damage_override=base_dmg,
                element_override=dot.element,
            )

            if dot.is_break_induced:
                damage = int(damage * (1.0 + dot.break_effect_snapshot))

            log.append({
                "element": dot.element.name,
                "source": source.name,
                "base": base_dmg,
                "damage": damage,
                "stacks": dot.stacks,
            })
            dot.duration -= 1
            if dot.duration > 0:
                remaining.append(dot)

        enemy.dot_statuses = remaining
        return log

    # --- 回能输入点 ---

    def on_kill(self, character: "Character") -> float:
        """击杀回能。"""
        return character.gain_energy(ENERGY_ON_KILL)

    def on_hit(self, character: "Character", base_amount: float | None = None) -> float:
        """受击回能。"""
        amount = base_amount if base_amount is not None else ENERGY_ON_HIT
        return character.gain_energy(amount, affected_by_err=True)

    # --- 死亡事件 ---

    def _notify_death(self, target: "Fighter", source: "Fighter") -> None:
        """发出 BEFORE_DEATH 和 UNIT_DOWNED 事件。"""
        if self.event_bus is None:
            return
        if not getattr(target, "_before_death_emitted", False):
            self.event_bus.emit(EventType.BEFORE_DEATH, unit=target, source=source)
            if hasattr(target, "_before_death_emitted"):
                target._before_death_emitted = True
        self.event_bus.emit(EventType.UNIT_DOWNED, unit=target, source=source)

    # --- 治疗结算 ---

    def calculate_and_apply_heal(
        self,
        healer: "Character",
        target: "Fighter",
        base_stat_amount: float,
        percentage: float,
        flat_addition: float = 0.0,
    ) -> int:
        """计算并执行治疗。

        Base Heal = base_stat_amount * percentage + flat_addition
        Multiplier = 1 + OUTGOING + INCOMING - INCOMING_REDUCTION
        返回实际恢复的 HP 值。
        """
        base_heal = int(base_stat_amount * percentage + flat_addition)

        out_bonus = healer.stats.get_total_stat(StatType.OUTGOING_HEALING_BOOST)
        in_bonus = 0.0
        in_reduction = 0.0
        if hasattr(target, "stats"):
            in_bonus = target.stats.get_total_stat(StatType.INCOMING_HEALING_BOOST)
            in_reduction = target.stats.get_total_stat(StatType.INCOMING_HEALING_REDUCTION)

        mult = max(0.0, 1.0 + out_bonus + in_bonus - in_reduction)
        final_heal = int(base_heal * mult)

        actual = target.receive_heal(final_heal)
        if actual > 0 and self.event_bus is not None:
            self.event_bus.emit(EventType.HEAL_DONE, healer=healer, target=target, amount=actual)
        return actual

    @staticmethod
    def calculate_shield_value(
        caster: "Character",
        base_stat: float,
        scaling: float,
        flat_bonus: float = 0.0,
    ) -> float:
        """护盾值计算: (base_stat × scaling + flat) × (1 + SHIELD_BONUS)。"""
        bonus = caster.stats.get_total_stat(StatType.SHIELD_BONUS)
        return (base_stat * scaling + flat_bonus) * (1.0 + bonus)

    # --- 负面状态施加判定 ---

    def try_apply_debuff(
        self,
        attacker: "Character" | "Enemy",
        target: "Enemy" | "Character",
        base_chance: float,
        debuff_type: str = "",
    ) -> tuple[bool, float]:
        """负面状态施加概率判定。

        formula: base_chance × (1 + EHR) × (1 - EFFECT_RES) × (1 - TYPE_DEBUFF_RES)
        Returns: (is_applied, real_chance)
        """
        import random
        ehr = attacker.stats.get_total_stat(StatType.EFFECT_HIT_RATE)
        res = target.stats.get_total_stat(StatType.EFFECT_RES)

        db_res = 0.0
        if debuff_type:
            spec = DEBUFF_RES_MAP.get(debuff_type)
            if spec:
                db_res = target.stats.get_total_stat(spec)

        real_chance = base_chance * (1.0 + ehr) * (1.0 - res) * (1.0 - db_res)
        success = random.random() < real_chance
        return (success, real_chance)

    # --- 净化 (驱散) ---

    def dispel_one(self, target: "Fighter") -> bool:
        """移除目标上的一个负面效果。优先级: CC > debuff modifier > DoT。
        返回 True 表示成功移除了一项。
        """
        if not hasattr(target, "stats"):
            return False

        # Priority 1: CC 状态
        if hasattr(target, "cc_statuses") and target.cc_statuses:
            removed = target.cc_statuses.pop(0)
            print(f"  [净化] {target.name} 的 {removed.cc_type} 被驱散")
            return True

        # Priority 2: 可驱散的 debuff modifier
        dispellable = target.stats.find_dispellable()
        if dispellable:
            mod = dispellable[0]
            target.stats.remove_modifier(mod)
            print(f"  [净化] {target.name} 的 {mod.source} 被驱散")
            return True

        # Priority 3: DoT 状态
        if hasattr(target, "dot_statuses") and target.dot_statuses:
            removed = target.dot_statuses.pop(0)
            print(f"  [净化] {target.name} 的 DoT({removed.element.name}) 被驱散")
            return True

        return False

    def dispel_one_buff(self, target: "Fighter") -> bool:
        """移除目标上的一个增益效果（value>0 的可驱散 modifier）。
        用于 Return to Darkness (21031) 的暴击驱散效果。
        """
        if not hasattr(target, "stats"):
            return False
        for m in target.stats.active_modifiers:
            if m.dispellable and m.value > 0:
                target.stats.remove_modifier(m)
                print(f"  [驱散增益] {target.name} 的 {m.source} 被移除")
                return True
        return False

    # --- 冻结附加伤害结算 ---

    def resolve_freeze_dot_ticks(self, enemy: "Enemy") -> list[dict]:
        """冻结附加伤害: 每回合开始时结算, 使用 ADDITIONAL_DMG 乘区链。"""
        from entities.base import FreezeDotStatus

        log: list[dict] = []
        remaining: list[FreezeDotStatus] = []

        for fd in enemy.freeze_dot_statuses:
            attacker = fd.attacker
            if not attacker.is_alive:
                continue

            damage, _, _, _ = self.execute_action(
                character=attacker,
                action_type=ActionType.BASIC_ATTACK,
                target=enemy,
                skill_multiplier=fd.multiplier,
                damage_type=DamageType.ADDITIONAL_DMG,
                element_override=ElementType.ICE,
            )
            log.append({
                "source": attacker.name,
                "damage": damage,
                "multiplier": fd.multiplier,
            })
            fd.remaining_turns -= 1
            if fd.remaining_turns > 0:
                remaining.append(fd)

        enemy.freeze_dot_statuses = remaining
        return log

    # --- 存活查询 ---

    @property
    def alive_characters(self) -> list["Character"]:
        return [c for c in self.characters if c.is_alive]

    @property
    def alive_enemies(self) -> list["Enemy"]:
        return [e for e in self.enemies if e.is_alive]

    @property
    def all_fighters(self) -> list["Fighter"]:
        sprites = [
            c.memosprite for c in self.characters
            if c.memosprite is not None and c.memosprite.is_alive
        ]
        return self.alive_characters + self.alive_enemies + sprites + self.countdown_units  # type: ignore[return-value]

    # --- 战斗终止 ---

    @property
    def battle_ended(self) -> bool:
        if len(self.alive_characters) == 0:
            return True
        if len(self.alive_enemies) == 0 and not self.has_next_wave():
            return True
        return False

    @property
    def result(self) -> Optional[str]:
        if not self.alive_characters:
            return "lose"
        if not self.alive_enemies:
            return "win"
        return None

    # --- 波次系统 ---

    def wave_cleared(self) -> bool:
        return len(self.alive_enemies) == 0

    def has_next_wave(self) -> bool:
        return self.current_wave + 1 < len(self.waves)

    def start_next_wave(self) -> int:
        """切换到下一波敌人。返回剩余波数。"""
        from config.game_config import SP_CARRY_OVER_WAVES, SP_INITIAL

        self.current_wave += 1
        self.enemies = self.waves[self.current_wave]

        if not SP_CARRY_OVER_WAVES:
            self.skill_points = SP_INITIAL

        if self.event_bus is not None:
            self.event_bus.emit(EventType.WAVE_START, wave=self.current_wave)

        # AV 重置: 按实体标记, 非统一规则
        for fighter in self.all_fighters:
            if not fighter.av_keep_on_wave:
                fighter.reset_av()

        return len(self.waves) - self.current_wave - 1

    # --- 秘技接口 ---

    def register_technique(self, callback) -> None:
        self.technique_effects.append(callback)

    def apply_techniques(self) -> None:
        from config.game_config import AMBUSH_AV_DELAY

        for cb in self.technique_effects:
            cb(self)
        if self.is_ambush:
            for c in self.alive_characters:
                c.current_av += AMBUSH_AV_DELAY
