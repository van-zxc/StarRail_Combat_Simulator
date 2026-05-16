"""Aha — 欢愉体系的行动条实体 (倒计时对象)。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.enums import ActionType, DamageType, ElementType, PathType
from entities.base import Fighter

if TYPE_CHECKING:
    from core.game_state import GameState
    from entities.characters.base import BaseCharacter


class Aha(Fighter):
    """欢愉倒计时对象，Punchline > 0 时出现在行动条上。"""

    is_countdown: bool = True

    def __init__(self, state: "GameState") -> None:
        self.state = state
        spd = self._compute_spd()
        super().__init__("Aha", hp=9999, speed=int(spd))
        self.av_keep_on_wave = True

    def _compute_spd(self) -> float:
        elation_allies = sorted(
            [c for c in self.state.alive_characters if c.path == PathType.ELATION],
            key=lambda c: c.speed,
            reverse=True,
        )
        weights = [5.0, 10.0, 20.0, 40.0]
        spd = 80.0
        for i, ally in enumerate(elation_allies[:4]):
            spd += ally.speed / weights[i]
        return spd

    def recalc_av_for_wave_change(self) -> None:
        pass

    def _get_elation_participants(self) -> list["BaseCharacter"]:
        chars = [c for c in self.state.alive_characters if c.path == PathType.ELATION]
        chars = [c for c in chars if "elation" in getattr(c, "_skills", {})]
        chars.sort(key=lambda c: c.character_id)
        return chars

    def _let_there_be_laughter(self) -> None:
        import random

        all_targets = self.state.alive_enemies + self.state.alive_characters
        if not all_targets:
            return
        from entities.characters.base import BaseCharacter
        from entities.enemies.base import BaseEnemy

        print(f"  [Aha] 无人有可用 Elation 技能 → Let There Be Laughter!")
        for _ in range(10):
            if not self.state.alive_enemies:
                break
            tgt = random.choice(all_targets)
            if isinstance(tgt, BaseEnemy):
                skill_mult = 1.0
                dmg, _, _, _ = self.state.execute_action(
                    self.state.alive_characters[0] if self.state.alive_characters else self,
                    ActionType.TALENT,
                    tgt,
                    skill_mult,
                    damage_type=DamageType.ELATION,
                    element_override=ElementType.QUANTUM,
                )
                print(f"    → {tgt.name} 造成 {dmg} 欢愉伤害")
            elif isinstance(tgt, BaseCharacter):
                actual = tgt.take_damage(1)
                tgt.gain_energy(2, affected_by_err=False)
                print(f"    → {tgt.name} 造成 {actual} 点伤害 (回复 2 能量)")
            if not tgt.is_alive and isinstance(tgt, BaseEnemy):
                print(f"    >>> {tgt.name} 已被击败！")

    def execute_aha_turn(self) -> None:
        state = self.state
        participants = self._get_elation_participants()
        punchline_snapshot = state.punchline

        elation_chars = [
            c for c in state.alive_characters if c.path == PathType.ELATION
        ]

        for c in state.alive_characters:
            cc_statuses = getattr(c, "cc_statuses", [])
            if cc_statuses:
                c.cc_statuses = []
                print(f"  [Aha] 解除了 {c.name} 的 CC 状态")

        if not participants:
            self._let_there_be_laughter()
        else:
            total_damage = 0
            for unit in participants:
                skill_obj = unit._skills.get("elation")
                if skill_obj is None:
                    continue
                target = state.alive_enemies[0] if state.alive_enemies else None
                if target is None:
                    break
                skill_mult = getattr(skill_obj, "skill_multiplier", 1.0)
                dmg, _, _, _ = state.execute_action(
                    unit, ActionType.TALENT, target, skill_mult,
                    damage_type=DamageType.ELATION,
                )
                total_damage += dmg
                print(f"  [Aha] {unit.name} Elation 技能 → {target.name}: {dmg} 伤害")
                if not target.is_alive:
                    print(f"  >>> {target.name} 已被击败！")

            print(f"  [Aha Instant] 总伤: {total_damage}")

        for c in elation_chars:
            cb_list = getattr(c, "certified_bangers", [])
            from entities.base import CertifiedBanger
            cb_list.append(CertifiedBanger(value=punchline_snapshot, duration=2))
            c.certified_bangers = cb_list
            print(f"  [Aha] {c.name} 获得 Certified Banger (值={punchline_snapshot})")

        state.punchline = len(elation_chars)

    def execute_aha_extra_turn(self, fixed_punchline: int) -> None:
        state = self.state
        participants = self._get_elation_participants()

        original_punchline = state.punchline
        try:
            state.punchline = fixed_punchline

            for c in state.alive_characters:
                cc_statuses = getattr(c, "cc_statuses", [])
                if cc_statuses:
                    c.cc_statuses = []
                    print(f"  [Aha Extra Turn] 解除了 {c.name} 的 CC 状态")

            if not participants:
                self._let_there_be_laughter()
            else:
                for unit in participants:
                    skill_obj = unit._skills.get("elation")
                    if skill_obj is None:
                        continue
                    target = state.alive_enemies[0] if state.alive_enemies else None
                    if target is None:
                        break
                    skill_mult = getattr(skill_obj, "skill_multiplier", 1.0)
                    dmg, _, _, _ = state.execute_action(
                        unit, ActionType.TALENT, target, skill_mult,
                        damage_type=DamageType.ELATION,
                    )
                    print(f"  [Aha Extra Turn] {unit.name} → {target.name}: {dmg} 伤害")
        finally:
            state.punchline = original_punchline
