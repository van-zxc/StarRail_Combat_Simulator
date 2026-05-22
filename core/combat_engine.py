from __future__ import annotations
"""CombatEngine — 行动值推进 + 终极技插队 + 回合调度 + 日志。"""

from typing import Optional

from core.enums import ActionType, DamageType, ElementType, PathType, StatType
from core.events import EventBus, EventType
from config.game_config import CYCLE_0_DURATION, CYCLE_DURATION, ENERGY_ON_HIT
from core.toughness import BreakEffectHandler, CCProcessor, get_break_level_multiplier


_ACTION_NAMES: dict[ActionType, str] = {
    ActionType.BASIC_ATTACK: "普攻",
    ActionType.SKILL: "战技",
    ActionType.ULTIMATE: "终结技",
}


class CombatEngine:
    """行动值推进与回合调度核心，支持终极技无视 AV 插队。"""

    def __init__(self, state: "GameState") -> None:
        self.state = state
        self.turn_count: int = 0
        self.action_log: list[dict[str, object]] = []
        self.current_cycle: int = 0
        self.cycle_av_elapsed: float = 0.0
        self.event_bus = EventBus()
        self.state.event_bus = self.event_bus
        self._inject_event_bus()

    # ================================================================
    #  主循环
    # ================================================================
    def _inject_event_bus(self) -> None:
        """将 event_bus 注入所有 Fighter。"""
        for fighter in self.state.all_fighters:
            fighter.event_bus = self.event_bus

    def run(self) -> str:
        print("=" * 52)
        print("  《崩坏：星穹铁道》 — 回合制战斗模拟  (装备/面板版)")
        print("=" * 52)
        self._log_team_status()
        self._check_and_enqueue_ultimates()

        # 注册角色技能事件监听器 (必须在 BATTLE_START emit 之前)
        for char in self.state.alive_characters:
            for skill in getattr(char, "_skills", {}).values():
                if hasattr(skill, "on_combat_start"):
                    skill.on_combat_start(self.state)

        # 注册光锥特效事件监听器
        for char in self.state.alive_characters:
            if char.light_cone is not None and char.light_cone.effect is not None:
                lc = char.light_cone
                lc._init_path_key_map()
                if lc.path is not None and lc.path != char.path:
                    continue
                lc.effect.on_combat_start(self.state, char)

        self.event_bus.emit(EventType.BATTLE_START, engine=self)
        self.state.apply_techniques()

        # 初始化 Aha (欢愉体系)
        self._manage_aha()

        while not self.state.battle_ended:
            # ── Priority 1: 追加行动队列 ──
            while self.state.has_follow_up_action() and not self.state.battle_ended:
                char, skill_obj, _ = self.state.pop_next_follow_up_action()
                if char.is_cc_blocked:
                    print(f"  [拦截] {char.name} 处于控制状态，追加行动被阻断")
                    continue
                self._execute_character_turn(char, skill_obj=skill_obj, is_extra_turn=True)
            if self.state.battle_ended:
                break

            # ── Priority 2a: 额外回合 (一次一个) ──
            if self.state.has_extra_turn():
                char, skill_obj = self.state.pop_next_extra_turn()
                self._execute_character_turn(char, skill_obj=skill_obj, is_extra_turn=True)
                self._check_and_enqueue_ultimates()
                if self.state.battle_ended:
                    break

            # ── Priority 2b: 终极技插队 ──
            self._resolve_pending_ultimates()
            if self.state.battle_ended:
                break

            # ── Priority 3: AV 时间轴推进 ──
            if self.event_bus is not None:
                self.event_bus.emit(EventType.ON_BEFORE_ACTION_ORDER_RESOLVE, engine=self)
            actor = self._find_next_actor()
            advance_amount = actor.current_av
            self._advance_time(advance_amount)
            actor.reset_av()

            self.cycle_av_elapsed += advance_amount
            self._check_cycle_boundary()

            self.turn_count += 1
            print(
                f"\n--- 第 {self.turn_count} 回合 │ SP={self.state.skill_points}"
                f" │ 时间推进 {advance_amount:.1f} ---"
            )

            self.event_bus.emit(EventType.TURN_START, unit=actor, engine=self)
            self._decrement_modifiers_timing("owner_turn_start", unit=actor)

            if isinstance(actor, self._Character):
                if self._process_cc_turn_start_char(actor):
                    self._log_team_status()
                    self._check_and_enqueue_ultimates()
                    self.event_bus.emit(EventType.TURN_END, unit=actor, engine=self)
                    continue
                skill_obj = getattr(actor, "decide_skill", lambda s: None)(self.state)
                self._execute_character_turn(actor, skill_obj=skill_obj, is_extra_turn=False)
            elif getattr(actor, "is_countdown", False):
                self._execute_countdown_turn(actor)
            elif hasattr(actor, "is_memosprite"):
                self._execute_memosprite_turn(actor)
            else:
                self._resolve_freeze_dots(actor)
                self._resolve_enemy_dot_ticks(actor)
                self._check_break_recovery(actor)
                if self._process_cc_turn_start(actor):
                    self._log_team_status()
                    self._check_and_enqueue_ultimates()
                    continue
                self._execute_enemy_turn(actor)

            self._log_team_status()

            # 修饰器削层 (仅当前行动者)
            self._decrement_modifiers(unit=actor)
            self._check_and_enqueue_ultimates()
            self.event_bus.emit(EventType.TURN_END, unit=actor, engine=self)

            # 波间切换
            if self.state.wave_cleared() and self.state.has_next_wave():
                print(f"\n  >>> 第 {self.state.current_wave} 波敌人已清除！进入第 {self.state.current_wave + 1} 波")
                self.state.start_next_wave()
                self._manage_aha()

        self.event_bus.emit(EventType.BATTLE_END, engine=self)
        self.event_bus.clear_all()
        return self._conclude()

    # ── 类型缓存（避免运行时循环导入） ──
    @property
    def _Character(self):
        from entities.characters.base import BaseCharacter
        return BaseCharacter

    # ================================================================
    #  终极技管理
    # ================================================================
    def _check_and_enqueue_ultimates(self) -> None:
        for char in self.state.alive_characters:
            if char.is_ultimate_ready:
                self.state.declare_ultimate(char)

    def _resolve_pending_ultimates(self) -> None:
        while self.state.has_pending_ultimates():
            char = self.state.pop_next_ultimate()
            if char is None or not char.is_alive:
                continue
            self._execute_ultimate_turn(char)
            self._check_and_enqueue_ultimates()
            if self.state.battle_ended:
                break

    # ================================================================
    #  行动值推进
    # ================================================================
    def _find_next_actor(self) -> "Fighter":
        # LIFO: 同 AV 时最后归零者先动 (§18.3)
        fighters = self.state.all_fighters
        return min(fighters, key=lambda f: (f.current_av, -f._av_zero_ts))

    def _advance_time(self, amount: float) -> None:
        for fighter in self.state.all_fighters:
            fighter.current_av -= amount

    # ================================================================
    #  轮次管理
    # ================================================================
    def _check_cycle_boundary(self) -> None:
        threshold = CYCLE_0_DURATION if self.current_cycle == 0 else CYCLE_DURATION
        while self.cycle_av_elapsed >= threshold:
            self.cycle_av_elapsed -= threshold
            self.current_cycle += 1
            threshold = CYCLE_DURATION
            print(f"  >>> 进入第 {self.current_cycle} 轮")

    # ================================================================
    #  修饰器削层
    # ================================================================
    def _decrement_modifiers(self, unit: "Fighter | None" = None) -> None:
        """回合结束时递减修饰器。unit 不为空时只处理该单位。"""
        self._decrement_modifiers_timing("owner_turn_end", unit=unit)

    def _decrement_modifiers_timing(self, timing: str, unit: "Fighter | None" = None) -> None:
        """按指定 tickTiming 递减修饰器。unit 不为空时只处理该单位。"""
        fighters = [unit] if unit is not None else self.state.all_fighters
        for fighter in fighters:
            if hasattr(fighter, "stats"):
                remaining = []
                expired_mods: list["StatModifier"] = []
                for m in fighter.stats.active_modifiers:
                    if not m.applied_this_turn and m.tick_timing == timing:
                        if m.duration is not None and m.duration > 0:
                            m.duration -= 1
                            if m.duration > 0:
                                remaining.append(m)
                            else:
                                expired_mods.append(m)
                            continue
                    remaining.append(m)
                    m.applied_this_turn = False
                fighter.stats.active_modifiers = remaining
                for m in expired_mods:
                    self.event_bus.emit(EventType.ON_STATUS_EXPIRE, unit=fighter, modifier=m)

            # CertifiedBanger 持续时间递减
            cb_list = getattr(fighter, "certified_bangers", [])
            if cb_list:
                new_cb = []
                for cb in cb_list:
                    cb.duration -= 1
                    if cb.duration > 0:
                        new_cb.append(cb)
                fighter.certified_bangers = new_cb

            # ShieldStatus 持续时间递减
            shield_list = getattr(fighter, "shield_statuses", [])
            if shield_list:
                expired = [s for s in shield_list if s.duration is not None and s.duration > 0]
                for s in expired:
                    s.duration -= 1  # type: ignore[operator]
                fighter.shield_statuses = [s for s in shield_list if s.duration is None or s.duration > 0]
                # March7th 护盾消失 → 重置外部嘲讽因子
                has_m7_shield = any(
                    s.source_name == "March7th_Shield" and s.shield_value > 0
                    for s in fighter.shield_statuses
                )
                if not has_m7_shield:
                    fighter.external_taunt_factor = 1.0

    # ================================================================
    #  Aha / 倒计时对象管理
    # ================================================================
    def _manage_aha(self) -> None:
        """管理 Aha 生命周期: Elation 角色存在时加入 countdown_units。"""
        from entities.aha import Aha
        elation_count = sum(1 for c in self.state.alive_characters if c.path == PathType.ELATION)
        if elation_count > 0:
            existing = [u for u in self.state.countdown_units if isinstance(u, Aha)]
            if not existing:
                aha = Aha(self.state)
                aha.event_bus = self.event_bus
                self.state.countdown_units.append(aha)
                self.state.punchline = elation_count
                print(f"  [Aha] 入场！Punchline 初始值 = {elation_count}，SPD = {aha.speed:.1f}")
            elif self.state.punchline == 0:
                self.state.punchline = elation_count

    def _execute_countdown_turn(self, actor: "Fighter") -> None:
        """倒计时对象行动: 目前仅有 Aha 的 Aha Instant。"""
        from entities.aha import Aha
        if isinstance(actor, Aha):
            print(f"\n  >>> Aha Instant 触发！Punchline = {self.state.punchline}")
            actor.execute_aha_turn()
            print(f"  [Aha] 结算后 Punchline = {self.state.punchline}")
            # 若已无 Elation 角色, 移除 Aha
            elation_count = sum(1 for c in self.state.alive_characters if c.path == PathType.ELATION)
            if elation_count == 0:
                self.state.countdown_units = [u for u in self.state.countdown_units if not isinstance(u, Aha)]
                print("  [Aha] 无欢愉角色, 离场")

    # ================================================================
    #  回合执行
    # ================================================================
    def _execute_character_turn(
        self, char: "Character", skill_obj: object = None,
        is_extra_turn: bool = False,
    ) -> None:
        """执行角色回合。extra_turn 时 AV 不重置、修饰器不削层。"""
        targets = self.state.alive_enemies
        if not targets:
            return
        self.event_bus.emit(EventType.ON_BEFORE_TARGET_SELECT, unit=char, targets=targets)
        target = targets[0]
        self.event_bus.emit(EventType.ON_AFTER_TARGET_SELECT, unit=char, target=target)

        if skill_obj is not None and hasattr(skill_obj, "hits"):
            # 多段攻击: 逐段 execute_multi_hit
            hits_list = getattr(skill_obj, "hits", [])
            action_type = getattr(skill_obj, "action_type", ActionType.BASIC_ATTACK)
            damage_type = getattr(skill_obj, "damage_type", DamageType.DIRECT)
            skill_tags = getattr(skill_obj, "tags", None)
            action_name = _ACTION_NAMES.get(action_type, "普攻")

            self.event_bus.emit(
                EventType.ACTION_START, unit=char, target=hits_list[0].target if hits_list else target,
                action_type=action_type, engine=self,
            )
            results = self.state.execute_multi_hit(
                char, hits_list, action_type=action_type,
                damage_type=damage_type, tags=skill_tags,
            )
            total_dmg = sum(r[0] for r in results)
            any_crit = any(r[1] for r in results)
            any_break = any(r[3] for r in results)
            crit_text = " 暴击！" if any_crit else ""
            print(f"{'  >>> 额外回合！' if is_extra_turn else '  '}{char.name} 使用【{action_name}】→ 多段 {total_dmg} 伤害{crit_text}")
            if any_break:
                self._apply_break_effects(char, target)
                print(f"  >>> {target.name} 被击破！")

            for r in results:
                self._log_action(char, action_type, r, 0, r[1], 0.0, r[3])

            self.event_bus.emit(
                EventType.AFTER_ACTION, unit=char, target=target,
                action_type=action_type, damage=total_dmg, is_crit=any_crit,
                engine=self,
            )
            return

        if skill_obj is not None and hasattr(skill_obj, "execute"):
            # 技能对象有自定义 execute → 直接调用, 不走标准管线
            damage, is_crit, toughness, is_break = skill_obj.execute(target, self.state)
            action_type = getattr(skill_obj, "action_type", ActionType.BASIC_ATTACK)
            action_name = _ACTION_NAMES.get(action_type, "普攻")
            self.event_bus.emit(
                EventType.ACTION_START, unit=char, target=target,
                action_type=action_type, engine=self,
            )
            self._log_action(char, action_type, target, damage, is_crit, toughness, is_break)
            crit_text = " 暴击！" if is_crit else ""
            toughness_text = f" 削韧 -{toughness:.0f}" if toughness > 0 else ""
            prefix = "  >>> 额外回合！" if is_extra_turn else "  "
            print(f"{prefix}{char.name} 使用【{action_name}】→ {target.name}，造成 {damage} 点伤害{crit_text}{toughness_text}")
            self.event_bus.emit(
                EventType.AFTER_ACTION, unit=char, target=target,
                action_type=action_type, damage=damage, is_crit=is_crit,
                engine=self,
            )
            return

        if skill_obj is not None:
            action_type = getattr(skill_obj, "action_type", ActionType.BASIC_ATTACK)
            skill_mult = getattr(skill_obj, "skill_multiplier", 1.0)
            action_name = _ACTION_NAMES.get(action_type, "普攻")
            sp_hint = ""
        elif self.state.skill_points > 0:
            action_type = ActionType.SKILL
            action_name = _ACTION_NAMES[action_type]
            sp_hint = ""
            skill_mult = 2.0
        else:
            action_type = ActionType.BASIC_ATTACK
            action_name = _ACTION_NAMES[action_type]
            sp_hint = "（SP不足）"
            skill_mult = 1.0

        self.event_bus.emit(
            EventType.ACTION_START, unit=char, target=target,
            action_type=action_type, engine=self,
        )

        damage, is_crit, toughness, is_break = self.state.execute_action(
            char, action_type, target, skill_mult,
        )
        self._log_action(char, action_type, target, damage, is_crit, toughness, is_break)

        crit_text = " 暴击！" if is_crit else ""
        toughness_text = f" 削韧 -{toughness:.0f}" if toughness > 0 else ""
        prefix = "  >>> 额外回合！" if is_extra_turn else "  "
        print(f"{prefix}{char.name} 使用【{action_name}】→ {target.name}，造成 {damage} 点伤害{crit_text}{toughness_text}{sp_hint}")
        if is_break:
            self._apply_break_effects(char, target)
            print(f"  >>> {target.name} 被击破！")

        # 连携攻击: 同一 AV 帧内按序结算 (各用自身面板, 不耗 SP/能量)
        joint_attackers = self.state.get_joint_attackers(char)
        for j in joint_attackers:
            if not j.is_alive or j.is_cc_blocked:
                continue
            j_dmg, j_crit, _, _ = self.state.execute_action(
                j, action_type, target, skill_mult,
                tags={"attack", "joint"},
            )
            self._log_action(j, action_type, target, j_dmg, j_crit, 0.0, False)
            j_crit_text = " 暴击！" if j_crit else ""
            print(f"    └ 连携 {j.name} 使用【{action_name}】→ {target.name}，造成 {j_dmg} 点伤害{j_crit_text}")
            if not target.is_alive:
                break

        if not target.is_alive:
            print(f"  >>> {target.name} 已被击败！")

        self.event_bus.emit(
            EventType.AFTER_ACTION, unit=char, target=target,
            action_type=action_type, damage=damage, is_crit=is_crit,
            engine=self,
        )

    def _resolve_enemy_dot_ticks(self, enemy: "Enemy") -> None:
        dot_logs = self.state.resolve_enemy_dot_ticks(enemy)
        for entry in dot_logs:
            self._log_dot_tick(enemy, entry)
            print(
                f"  [DoT {entry['element']}] {entry['source']} → {enemy.name}，"
                f"基础 {entry['base']}，层数 {entry['stacks']}，造成 {entry['damage']} 点伤害"
            )

    def _resolve_freeze_dots(self, enemy: "Enemy") -> None:
        """结算冻结附加伤害。"""
        logs = self.state.resolve_freeze_dot_ticks(enemy)
        for entry in logs:
            print(
                f"  [冻结附加] {entry['source']} → {enemy.name}，"
                f"倍率 {entry['multiplier']:.0%}，造成 {entry['damage']} 点伤害"
            )

    def _check_break_recovery(self, enemy: "Enemy") -> None:
        BreakEffectHandler.recover(enemy)

    def _process_cc_turn_start(self, enemy: "Enemy") -> bool:
        """处理敌方回合初 CC 状态。返回 True 表示本次行动被跳过。"""
        return CCProcessor.process_enemy(enemy, self)

    def _process_cc_turn_start_char(self, char: "Character") -> bool:
        """处理角色回合初 CC 状态。返回 True 表示本次行动被跳过。"""
        return CCProcessor.process_character(char)

    def _execute_memosprite_turn(self, sprite: "Memosprite") -> None:
        """忆灵回合：使用基础攻击 (日后扩展为 Memosprite Skill)。"""
        targets = self.state.alive_enemies
        if not targets:
            return
        target = targets[0]
        damage, is_crit, _, _ = self.state.execute_action(
            sprite, ActionType.BASIC_ATTACK, target, 1.0,
        )
        self._log_action(sprite, ActionType.BASIC_ATTACK, target, damage, is_crit, 0.0, False)
        print(f"  [忆灵] {sprite.name} 攻击 → {target.name}，造成 {damage} 点伤害")

    def _execute_enemy_turn(self, enemy: "Enemy") -> None:
        target_name, damage = enemy.attack(self.state.characters)
        if not target_name:
            return
        self._log_action(enemy, None, target_name, damage, False, 0.0, False)
        victim = next((c for c in self.state.characters if c.name == target_name), None)
        print(f"  {enemy.name} 攻击 → {target_name}，造成 {damage} 点伤害")
        if victim:
            self.state.on_hit(victim, base_amount=enemy.hit_energy_bucket)
            self.event_bus.emit(EventType.ON_HIT, source=enemy, target=victim,
                                damage=damage, action_type=None, damage_type=DamageType.DIRECT)
        if victim and not victim.is_alive:
            self.state._notify_death(victim, enemy)
            self.event_bus.emit(EventType.ON_KILL, source=enemy, target=victim)
            print(f"  >>> {victim.name} 已被击败！")

    def _execute_ultimate_turn(self, char: "Character") -> None:
        targets = self.state.alive_enemies
        if not targets:
            return
        target = targets[0]
        self.event_bus.emit(EventType.ON_ULTIMATE_INSERTED, character=char, target=target)

        ultimate_skill = getattr(char, "_skills", {}).get("ultimate")
        if ultimate_skill is not None and hasattr(ultimate_skill, "execute"):
            damage, is_crit, toughness, is_break = ultimate_skill.execute(target, self.state)
        else:
            ult_mult = getattr(ultimate_skill, "skill_multiplier", 3.0) if ultimate_skill else 3.0
            damage, is_crit, toughness, is_break = self.state.execute_action(
                char, ActionType.ULTIMATE, target, ult_mult,
            )

        self._log_action(char, ActionType.ULTIMATE, target, damage, is_crit, toughness, is_break)
        crit_text = " 暴击！" if is_crit else ""
        toughness_text = f" 削韧 -{toughness:.0f}" if toughness > 0 else ""
        print(f"  >>> 终结技插队！{char.name} 使用【终结技】→ {target.name}，造成 {damage} 点伤害{crit_text}{toughness_text}")
        if is_break:
            self._apply_break_effects(char, target)
            print(f"  >>> {target.name} 被击破！")
        if not target.is_alive:
            print(f"  >>> {target.name} 已被击败！")

    def _get_level_multiplier(self, level: int) -> float:
        return get_break_level_multiplier(level)

    def _apply_break_effects(self, char: "Character", target: "Enemy") -> None:
        BreakEffectHandler.apply(self, char, target)

    # ================================================================
    #  动作日志
    # ================================================================
    def _log_action(self, actor, action_type, target, damage,
                    is_crit=False, toughness=0.0, is_break=False):
        self.action_log.append({
            "turn": self.turn_count,
            "actor": actor.name,
            "action": action_type.name if action_type else "ENEMY_ATTACK",
            "target": target if isinstance(target, str) else target.name,
            "damage": damage,
            "crit": is_crit,
            "toughness": toughness,
            "break": is_break,
        })

    def _log_dot_tick(self, enemy, entry):
        self.action_log.append({
            "turn": self.turn_count,
            "actor": entry["source"],
            "action": "DOT_TICK",
            "target": enemy.name,
            "damage": entry["damage"],
            "dot_element": entry["element"],
            "dot_base": entry["base"],
            "dot_stacks": entry["stacks"],
        })

    # ================================================================
    #  日志与结算
    # ================================================================
    def _log_team_status(self) -> None:
        char_status = " │ ".join(
            f"{c.name}: HP={c.hp}/{c.max_hp} E={c.energy}/{c.max_energy} AV={c.current_av:.1f}"
            for c in self.state.characters
        )
        # 忆灵状态
        sprite_parts = []
        for c in self.state.characters:
            if c.memosprite is not None:
                s = c.memosprite
                sprite_parts.append(f"{s.name}: HP={s.hp}/{s.max_hp} AV={s.current_av:.1f}")
        enemy_parts = []
        for e in self.state.enemies:
            if e.broken:
                t_info = "[击破]"
            elif e.max_toughness > 0:
                t_info = f"T={e.current_toughness:.0f}/{e.max_toughness:.0f}"
            else:
                t_info = ""
            enemy_parts.append(f"{e.name}: HP={e.hp}/{e.max_hp} {t_info} AV={e.current_av:.1f}")
        print(f"  己方: {char_status}")
        if sprite_parts:
            print(f"  忆灵: {' │ '.join(sprite_parts)}")
        print(f"  敌方: {' │ '.join(enemy_parts)}")

    def _conclude(self) -> str:
        result = self.state.result or "draw"
        print("\n" + "=" * 52)
        print("  战斗胜利！所有敌人已被击破。" if result == "win" else "  战斗失败... 己方全灭。")
        print("=" * 52)
        return result
