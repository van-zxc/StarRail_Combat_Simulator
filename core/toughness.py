from __future__ import annotations
"""击破与 CC 处理 — 从 CombatEngine 拆出, 保持纯函数风格。"""

from typing import TYPE_CHECKING

from core.enums import ActionType, DamageType, ElementType, StatType
from entities.base import CCStatus, DoTStatus

if TYPE_CHECKING:
    from core.combat_engine import CombatEngine
    from core.game_state import GameState
    from entities.characters.base import BaseCharacter
    from entities.enemies.base import BaseEnemy
    from entities.base import Fighter


# ── Break Level Multiplier 表 ──

_BREAK_LM: dict[int, float] = {
    1:54,2:58,3:62,4:67.5264,5:70.5094,6:73.5228,7:76.566,8:79.6385,9:82.7395,10:85.8684,
    11:91.4944,12:97.068,13:102.5892,14:108.0579,15:113.4743,16:118.8383,17:124.1499,
    18:129.4091,19:134.6159,20:139.7703,21:149.3323,22:158.8011,23:168.1768,24:177.4594,
    25:186.6489,26:195.7452,27:204.7484,28:213.6585,29:222.4754,30:231.1992,
    31:246.4276,32:261.181,33:275.4733,34:289.3179,35:302.7275,36:315.7144,37:328.2905,
    38:340.4671,39:352.2554,40:363.6658,41:408.124,42:451.7883,43:494.6798,
    44:536.8188,45:578.2249,46:618.9172,47:658.9138,48:698.2325,49:736.8905,
    50:774.9041,51:871.0599,52:964.8705,53:1056.4206,54:1145.791,55:1233.0585,
    56:1318.2965,57:1401.575,58:1482.9608,59:1562.5178,60:1640.3068,61:1752.3215,
    62:1861.9011,63:1969.1242,64:2074.0659,65:2176.7983,66:2277.3904,67:2375.9085,
    68:2472.416,69:2566.9739,70:2659.6406,71:2780.3044,72:2898.6022,73:3014.6029,
    74:3128.3729,75:3239.9758,76:3349.473,77:3456.9236,78:3562.3843,79:3665.9099,
    80:3767.5533,81:3957.8618,82:4155.2118,83:4359.8638,84:4572.0878,85:4792.1641,
    86:5020.3833,87:5257.0466,88:5502.4664,89:5756.9667,90:6020.8836,91:6294.5654,
    92:6578.3734,93:6872.6823,94:7177.8806,95:7494.3713,
}


def get_break_level_multiplier(level: int) -> float:
    return _BREAK_LM.get(level, _BREAK_LM[1])


# ── 击破效果 ──

class BreakEffectHandler:
    """击破伤害、元素 Debuff、推条、Broken 恢复。"""

    @staticmethod
    def _cc_resisted(target) -> bool:
        import random
        if hasattr(target, "stats"):
            resist = target.stats.get_total_stat(StatType.CC_RESIST)
            if resist > 0:
                return random.random() < resist
        return False

    @staticmethod
    def apply(
        engine: "CombatEngine",
        char: "BaseCharacter",
        target: "BaseEnemy",
    ) -> None:
        from core.damage.multipliers import _ELEMENT_BREAK_DMG_MULT

        element = char.element
        be = char.stats.get_total_stat(StatType.BREAK_EFFECT)
        tm = 0.5 + target.max_toughness / 40.0
        lm = get_break_level_multiplier(char.level)

        elem_mult = _ELEMENT_BREAK_DMG_MULT.get(element, 1.0)
        base_break = int(elem_mult * lm * tm)

        # 推条
        target.delay_action(0.25)

        # DoT 型 Debuff
        if element in (ElementType.PHYSICAL, ElementType.FIRE,
                        ElementType.LIGHTNING, ElementType.WIND):
            dot_base = lm
            stacks = 1
            dur = 2
            if element == ElementType.WIND:
                stacks = 3
            elif element == ElementType.LIGHTNING:
                dot_base = 2.0 * lm

            dot = DoTStatus(
                source_character=char, element=element,
                dot_multiplier=dot_base, stacks=stacks, duration=dur,
                is_break_induced=True, break_effect_snapshot=be,
            )
            if element == ElementType.PHYSICAL:
                max_cap = 2.0 * lm * tm
                dot.dot_multiplier = min(0.07 * target.max_hp, max_cap)
            target.apply_dot(dot)
            dot_names = {
                ElementType.PHYSICAL: "裂伤", ElementType.FIRE: "灼烧",
                ElementType.LIGHTNING: "触电", ElementType.WIND: "风化",
            }
            print(f"  >>> 击破挂载【{dot_names[element]}】×{stacks}, 持续{dur}回合")

        # CC 型 Debuff
        elif element == ElementType.ICE:
            if not BreakEffectHandler._cc_resisted(target):
                target.cc_statuses.append(
                    CCStatus("Freeze", remaining_turns=1, break_effect_snapshot=be))
                print(f"  >>> 击破挂载【冻结】, 持续1回合")
        elif element == ElementType.QUANTUM:
            if not BreakEffectHandler._cc_resisted(target):
                target.cc_statuses.append(
                    CCStatus("Entanglement", remaining_turns=1, stacks=1,
                              break_effect_snapshot=be))
                extra = 0.20 * (1.0 + be)
                target.delay_action(extra)
                print(f"  >>> 击破挂载【纠缠】, 额外推条 {extra*100:.1f}%")
        elif element == ElementType.IMAGINARY:
            if not BreakEffectHandler._cc_resisted(target):
                target.cc_statuses.append(
                    CCStatus("Imprison", remaining_turns=1, break_effect_snapshot=be))
                extra = 0.30 * (1.0 + be)
                target.delay_action(extra)
                print(f"  >>> 击破挂载【禁锢】, 额外推条 {extra*100:.1f}%")

        if base_break > 0:
            bdmg, _, _, _ = engine.state.execute_action(
                char, ActionType.BASIC_ATTACK, target, 1.0,
                damage_type=DamageType.BREAK,
                base_damage_override=base_break,
                element_override=element,
            )
            print(f"  >>> 击破伤害: {bdmg} ({element.name} ×{elem_mult})")

    @staticmethod
    def recover(target: "BaseEnemy") -> None:
        if target.broken:
            target.broken = False
            target.current_toughness = target.max_toughness
            print(f"  >>> {target.name} 从击破状态恢复，韧性回复至 {target.max_toughness:.0f}")


# ── CC 处理 ──

class CCProcessor:
    """冻结/禁锢/纠缠的回合初处理。"""

    @staticmethod
    def process_enemy(enemy: "BaseEnemy", engine: "CombatEngine") -> bool:
        """处理敌方回合初 CC。返回 True 表示行动被跳过。"""
        skip_turn = False
        remaining = []
        for cc in enemy.cc_statuses:
            if cc.cc_type == "Freeze":
                lm = get_break_level_multiplier(80)
                base_dmg = int(1.0 * lm)
                actual = enemy.take_damage(base_dmg)
                print(f"  >>> 冻结伤害: {actual}")
                if not enemy.is_alive and engine.event_bus is not None:
                    engine.state._notify_death(enemy, enemy)
                enemy.advance_action(0.50)
                skip_turn = True
            elif cc.cc_type == "Entanglement":
                lm = get_break_level_multiplier(80)
                tm = 0.5 + enemy.max_toughness / 40.0
                base_dmg = int(0.6 * cc.stacks * lm * tm * (1.0 + cc.break_effect_snapshot))
                actual = enemy.take_damage(base_dmg)
                print(f"  >>> 纠缠附加伤害: {actual} (层数 {cc.stacks})")
                if not enemy.is_alive and engine.event_bus is not None:
                    engine.state._notify_death(enemy, enemy)
            elif cc.cc_type == "Imprison":
                from entities.base import StatModifier as SM
                from core.enums import StatModifierType as SMT, StatType as ST
                slow = SM(ST.SPD, SMT.PERCENT, -0.10, source="Imprison")
                slow.duration = 1
                enemy.stats.add_modifier(slow)
                print(f"  >>> 禁锢减速: SPD -10%")
            cc.remaining_turns -= 1
            if cc.remaining_turns > 0:
                remaining.append(cc)
        enemy.cc_statuses = remaining
        return skip_turn

    @staticmethod
    def process_character(char: "BaseCharacter") -> bool:
        """处理角色回合初 CC。返回 True 表示行动被跳过。"""
        skip_turn = False
        remaining = []
        for cc in char.cc_statuses:
            if cc.cc_type == "Freeze":
                print(f"  >>> {char.name} 处于冻结状态，行动跳过")
                skip_turn = True
            elif cc.cc_type == "Imprison":
                from entities.base import StatModifier as SM
                from core.enums import StatModifierType as SMT, StatType as ST
                slow = SM(ST.SPD, SMT.PERCENT, -0.10, source="Imprison")
                slow.duration = 1
                char.stats.add_modifier(slow)
                print(f"  >>> {char.name} 禁锢减速: SPD -10%")
            cc.remaining_turns -= 1
            if cc.remaining_turns > 0:
                remaining.append(cc)
        char.cc_statuses = remaining
        return skip_turn
