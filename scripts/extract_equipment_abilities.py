"""Extract structured data from EquipmemtAbility.json for all 60+ light cone abilities."""
from __future__ import annotations

import json
import sys
from collections import OrderedDict

JSON_PATH = r"E:\starail_trial\original_data\turnbasedgamedata_combat\Config\ConfigAbility\EquipmemtAbility.json"


def resolve_dv(ability: dict, hash_str: str) -> str:
    """Resolve a dynamic values hash to its ReadInfo.Type."""
    dv = ability.get("DynamicValues", {})
    vals = dv.get("Values", {})
    entry = vals.get(hash_str, {})
    ri = entry.get("ReadInfo", {})
    dtype = ri.get("Type", "?")
    if dtype == "None" or dtype is None:
        return "None"
    if dtype == "SkillTreeParam":
        return "SkillTreeParam"
    if dtype == "SkillRank":
        return "SkillRank"
    if dtype == "BattleEvent":
        return "BattleEvent"
    if dtype == "FloorCustomData":
        return "FloorCustomData"
    if dtype == "ClientOnly":
        return "ClientOnly"
    return dtype or "?"


def resolve_dv_from_postfix(ability: dict, postfix: dict | None, mod_data: dict = None) -> str:
    """Resolve DynamicHashes in a PostfixExpr to their types.
    Checks ability-level first, then modifier-level DynamicValues."""
    if not postfix:
        return ""
    hashes = postfix.get("DynamicHashes", [])
    if not hashes:
        return "?"
    parts = []
    for h in hashes:
        hstr = str(h)
        # Check ability-level first
        dv = ability.get("DynamicValues", {}).get("Values", {})
        entry = dv.get(hstr, {})
        ri = entry.get("ReadInfo", {})
        dtype = ri.get("Type")
        if dtype is not None and dtype != "":
            parts.append(ri.get("Type") or f"{{{hstr}:?}}")
            continue
        # Check modifier-level
        if mod_data:
            mdv = mod_data.get("DynamicValues", {}).get("Values", {})
            mentry = mdv.get(hstr, {})
            mri = mentry.get("ReadInfo", {})
            mdtype = mri.get("Type")
            if mdtype is not None and mdtype != "":
                parts.append(f"Mod.{mdtype}")
                continue
            # Even if ReadInfo is missing, the hash might map to a value
            if mentry:
                parts.append(f"Mod.{{{hstr}}}")
                continue
        parts.append(f"{{{hstr}}}")
    return ", ".join(parts)


def extract_target_alias(target: dict | None) -> str:
    """Extract the Alias string from a TargetType dict."""
    if not target:
        return "?"
    if target.get("$type") == "RPG.GameCore.TargetAlias":
        return target.get("Alias", "?")
    if target.get("$type") == "RPG.GameCore.TargetConcat":
        targets = target.get("Targets", [])
        aliases = [extract_target_alias(t) for t in targets]
        return "(" + " + ".join(aliases) + ")"
    return f"??{target.get('$type', 'N/A')}"


def extract_task(task: dict, ability: dict, mod_data: dict = None, indent: str = "          ") -> list[str]:
    """Extract info from a single task/action dict."""
    lines = []
    ttype = task.get("$type", "")

    if ttype == "RPG.GameCore.StackProperty":
        prop = task.get("Property", "?")
        target = extract_target_alias(task.get("TargetType"))
        dv = resolve_dv_from_postfix(ability, task.get("PropertyValue", {}).get("PostfixExpr"), mod_data)
        lines.append(f"{indent}StackProperty: {prop} → {target} [DV: {dv}]")

    elif ttype == "RPG.GameCore.AddModifier":
        mod_name = task.get("ModifierName", "?")
        target = extract_target_alias(task.get("TargetType"))
        dv_hint = ""
        mod_dvs = task.get("DynamicValues", {})
        if mod_dvs:
            for k, v in mod_dvs.items():
                pf = v.get("PostfixExpr")
                d = resolve_dv_from_postfix(ability, pf, mod_data)
                dv_hint += f" ({k}: {d})"
        lines.append(f"{indent}AddModifier: {mod_name} → {target}{dv_hint}")

    elif ttype == "RPG.GameCore.RemoveModifier":
        mod_name = task.get("ModifierName", "?")
        target = extract_target_alias(task.get("TargetType"))
        flags = []
        if task.get("OnlyRemoveCasterAdded"):
            flags.append("OnlyRemoveCasterAdded")
        if task.get("RemoveOnlyOnExitBattle"):
            flags.append("RemoveOnlyOnExitBattle")
        lines.append(f"{indent}RemoveModifier: {mod_name} → {target}" + (f" [{', '.join(flags)}]" if flags else ""))

    elif ttype == "RPG.GameCore.ModifyDamageData":
        target = extract_target_alias(task.get("TargetType"))
        for k in task:
            if k.startswith("Attacker_") or k.startswith("Defender_") or k.startswith("Target_"):
                dv = resolve_dv_from_postfix(ability, task[k].get("PostfixExpr"), mod_data)
                lines.append(f"{indent}ModifyDamageData.{k} → {target} [DV: {dv}]")
            elif k.startswith("DamageValue_"):
                lines.append(f"{indent}ModifyDamageData.{k} → {target}")

    elif ttype == "RPG.GameCore.ModifyHealData":
        lines.append(f"{indent}ModifyHealData → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.HealHP":
        target = extract_target_alias(task.get("TargetType"))
        lines.append(f"{indent}HealHP → {target}")

    elif ttype == "RPG.GameCore.Retarget":
        target = extract_target_alias(task.get("TargetType"))
        attr = task.get("AttributeType", "")
        lines.append(f"{indent}Retarget → {target}" + (f" [Attr: {attr}]" if attr else ""))

    elif ttype == "RPG.GameCore.ModifyCurrentSkillDelayCost":
        target = extract_target_alias(task.get("TargetType"))
        lines.append(f"{indent}ModifyCurrentSkillDelayCost → {target}")

    elif ttype == "RPG.GameCore.ModifySPNew":
        target = extract_target_alias(task.get("TargetType"))
        lines.append(f"{indent}ModifySPNew → {target}")

    elif ttype == "RPG.GameCore.ModifyTeamBoostPoint":
        lines.append(f"{indent}ModifyTeamBoostPoint → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.ModifyActionDelay":
        lines.append(f"{indent}ModifyActionDelay → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.RemoveSelfModifier":
        lines.append(f"{indent}RemoveSelfModifier: {task.get('ModifierName', 'self')}")

    elif ttype == "RPG.GameCore.RemoveShield":
        lines.append(f"{indent}RemoveShield → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.InitShield":
        lines.append(f"{indent}InitShield → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetResilience":
        lines.append(f"{indent}SetResilience → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.TriggerEffect":
        lines.append(f"{indent}TriggerEffect → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.DamageByAttackProperty":
        lines.append(f"{indent}DamageByAttackProperty → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.AddBuffPerform":
        lines.append(f"{indent}AddBuffPerform → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.DefineDynamicValue":
        lines.append(f"{indent}DefineDynamicValue: {task.get('Name', '?')}")

    elif ttype == "RPG.GameCore.SetDynamicValue":
        target = extract_target_alias(task.get("TargetType"))
        lines.append(f"{indent}SetDynamicValue → {target}")

    elif ttype == "RPG.GameCore.SetDynamicValueByProperty":
        target = extract_target_alias(task.get("TargetType"))
        lines.append(f"{indent}SetDynamicValueByProperty → {target}")

    elif ttype == "RPG.GameCore.SetDynamicValueByHPRatio":
        lines.append(f"{indent}SetDynamicValueByHPRatio → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByAttackTargetCount":
        lines.append(f"{indent}SetDynamicValueByAttackTargetCount → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByCharacterCount":
        lines.append(f"{indent}SetDynamicValueByCharacterCount → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByDamageDataProperty":
        lines.append(f"{indent}SetDynamicValueByDamageDataProperty → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByHealDataProperty":
        lines.append(f"{indent}SetDynamicValueByHealDataProperty → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByBPChange":
        lines.append(f"{indent}SetDynamicValueByBPChange → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByCountOfBaseType":
        lines.append(f"{indent}SetDynamicValueByCountOfBaseType → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByModifierValue":
        lines.append(f"{indent}SetDynamicValueByModifierValue → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.SetDynamicValueByStatusCount":
        lines.append(f"{indent}SetDynamicValueByStatusCount → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.WaitSecond":
        lines.append(f"{indent}WaitSecond → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.LoopExecuteTaskList":
        lines.append(f"{indent}LoopExecuteTaskList")
        for subt in task.get("TaskList", []):
            lines.extend(extract_task(subt, ability, mod_data, indent + "  "))

    elif ttype == "RPG.GameCore.IncludeTaskListTemplate":
        lines.append(f"{indent}IncludeTaskListTemplate: {task.get('Name', '?')}")

    elif ttype == "RPG.GameCore.RandomConfig":
        lines.append(f"{indent}RandomConfig")
        for rtask in task.get("TaskList", []):
            lines.extend(extract_task(rtask, ability, mod_data, indent + "  "))

    elif ttype == "RPG.GameCore.PredicateTaskList":
        # Nested predicate task inside a success task list
        pred = task.get("Predicate")
        if pred:
            pred_str = extract_predicate(pred, ability)
            lines.append(f"{indent}IF {pred_str}:")
        stl = task.get("SuccessTaskList", [])
        for subt in stl:
            lines.extend(extract_task(subt, ability, mod_data, indent + "  "))
        ftl = task.get("FailedTaskList", [])
        if ftl:
            lines.append(f"{indent}ELSE:")
            for subt in ftl:
                lines.extend(extract_task(subt, ability, mod_data, indent + "  "))
        etl = task.get("ElseTaskList", [])
        if etl:
            lines.append(f"{indent}ELSE:")
            for subt in etl:
                lines.extend(extract_task(subt, ability, mod_data, indent + "  "))

    elif ttype == "RPG.GameCore.ModifierAttachEffect":
        lines.append(f"{indent}ModifierAttachEffect → {extract_target_alias(task.get('TargetType'))}")

    elif ttype == "RPG.GameCore.DispelStatus":
        target = extract_target_alias(task.get("TargetType"))
        lines.append(f"{indent}DispelStatus → {target}")

    else:
        lines.append(f"{indent}[UNKNOWN: {ttype}]")

    return lines


def extract_predicate(pred: dict, ability: dict) -> str:
    """Extract a human-readable predicate description."""
    ptype = pred.get("$type", "")
    if ptype == "RPG.GameCore.ByCurrentSkillType":
        return f"SkillType={pred.get('SkillType', '?')}"
    if ptype == "RPG.GameCore.ByAttackType":
        atypes = pred.get("AttackTypes", [])
        return f"AttackTypes={atypes}"
    if ptype == "RPG.GameCore.ByCompareHPRatio":
        ct = pred.get("CompareType", "?")
        cv = pred.get("CompareValue", {})
        if cv.get("IsDynamic") and cv.get("PostfixExpr"):
            dv = resolve_dv_from_postfix(ability, cv.get("PostfixExpr"))
            return f"HP_Ratio {ct} DV[{dv}]"
        elif cv.get("FixedValue"):
            return f"HP_Ratio {ct} {cv['FixedValue'].get('Value', '?')}"
        return f"HP_Ratio {ct} ?"
    if ptype == "RPG.GameCore.ByCompareWaveCount":
        ct = pred.get("CompareType", "?")
        cv = pred.get("CompareValue", {})
        if cv.get("FixedValue"):
            return f"WaveCount {ct} {cv['FixedValue'].get('Value', '?')}"
        return f"WaveCount {ct} ?"
    if ptype == "RPG.GameCore.ByIsTurnOwnerEntity":
        return "IsTurnOwner"
    if ptype == "RPG.GameCore.ByCheckModifierCallBackBehaviorFlag":
        return f"CheckBehaviorFlag={pred.get('BehaviorFlag', '?')}"
    if ptype == "RPG.GameCore.ByContainBehaviorFlag":
        return f"ContainBehaviorFlag={pred.get('BehaviorFlag', '?')}"
    if ptype == "RPG.GameCore.ByIsContainModifier":
        return f"IsContainModifier={pred.get('ModifierName', '?')}"
    if ptype == "RPG.GameCore.ByIsDamageCritical":
        return "IsDamageCritical"
    if ptype == "RPG.GameCore.ByIsTeammate":
        return "IsTeammate"
    if ptype == "RPG.GameCore.ByCompareAbilityProperty":
        return f"CompareAbilityProperty: {pred.get('Property', '?')}"
    if ptype == "RPG.GameCore.ByTargetTeam":
        return f"ByTargetTeam: {pred.get('TeamType', '?')}"
    if ptype == "RPG.GameCore.ByStatusCount":
        ct = pred.get("CompareType", "?")
        cv = pred.get("CompareValue", {})
        if cv.get("FixedValue"):
            return f"StatusCount {ct} {cv['FixedValue'].get('Value', '?')}"
        if cv.get("IsDynamic") and cv.get("PostfixExpr"):
            dv = resolve_dv_from_postfix(ability, cv.get("PostfixExpr"))
            return f"StatusCount {ct} DV[{dv}]"
        return f"StatusCount {ct} ?"
    if ptype == "RPG.GameCore.ByCompareDynamicValue":
        lhs = pred.get("DynamicKey", "")
        if not lhs:
            lhs = pred.get("LeftDynamicValue", {}).get("DynamicValueKey", "?")
        ct = pred.get("CompareType", "?")
        rhs = pred.get("CompareValue", {})
        if rhs.get("FixedValue"):
            rhs_v = rhs['FixedValue'].get('Value', '?')
        elif isinstance(rhs, dict):
            rhs_v = str(rhs.get("DynamicValueKey", "?"))
        else:
            rhs_v = str(rhs)
        return f"DynamicValue({lhs}) {ct} {rhs_v}"
    if ptype == "RPG.GameCore.ByTargetListIntersects":
        return "TargetListIntersects"
    if ptype == "RPG.GameCore.ByInTurnBasedGameModeState":
        gms = pred.get("GameModeState", {})
        if isinstance(gms, dict):
            return f"GameModeState={gms.get('GameModeState', '?')}"
        return f"GameModeState={gms}"
    if ptype == "RPG.GameCore.ByCompareSPRatio":
        ct = pred.get("CompareType", "?")
        cv = pred.get("CompareValue", {})
        if cv.get("FixedValue"):
            return f"SP_Ratio {ct} {cv['FixedValue'].get('Value', '?')}"
        if cv.get("IsDynamic") and cv.get("PostfixExpr"):
            dv = resolve_dv_from_postfix(ability, cv.get("PostfixExpr"))
            return f"SP_Ratio {ct} DV[{dv}]"
        return f"SP_Ratio {ct} ?"
    if ptype == "RPG.GameCore.ByCompareModifierValue":
        mn = pred.get("ModifierName", "?")
        ct = pred.get("CompareType", "?")
        return f"CompareModifierValue: {mn} {ct}"
    if ptype == "RPG.GameCore.ByCharacterDamageType":
        return f"CharacterDamageType={pred.get('DamageType', '?')}"
    if ptype == "RPG.GameCore.ByIsPropertyValueMinOrMax":
        return f"IsPropertyValueMinOrMax: {pred.get('Property', '?')}"
    if ptype == "RPG.GameCore.ByIsTopActionDelayTarget":
        return "IsTopActionDelayTarget"
    if ptype == "RPG.GameCore.ByRandomChance":
        return "RandomChance"
    if ptype == "RPG.GameCore.ByNot":
        sub = extract_predicate(pred.get("Predicate", {}), ability)
        return f"NOT[{sub}]"
    if ptype == "RPG.GameCore.ByCompareParamValue":
        param = pred.get("ParamType", "?")
        ct = pred.get("CompareType", "?")
        cv = pred.get("CompareValue", {})
        if cv.get("FixedValue"):
            return f"ParamValue({param}) {ct} {cv['FixedValue'].get('Value', '?')}"
        return f"ParamValue({param}) {ct} ?"
    if ptype == "RPG.GameCore.ByCompareTarget":
        target = extract_target_alias(pred.get("TargetType"))
        return f"CompareTarget: {target}"
    if ptype == "RPG.GameCore.ByCompareCurrentModifierStatusType":
        return f"CompareCurrentModifierStatusType={pred.get('StatusType', '?')}"
    if ptype == "RPG.GameCore.ByIsTargetValid":
        return "IsTargetValid"
    if ptype == "RPG.GameCore.ByContainsParamFlag":
        return f"ContainsParamFlag={pred.get('ParamFlag', '?')}"
    if ptype == "RPG.GameCore.ByAny":
        sub = []
        for sp in pred.get("PredicateList", []):
            sub.append(extract_predicate(sp, ability))
        return "AnyOf[" + " | ".join(sub) + "]"
    if ptype == "RPG.GameCore.ByAnd":
        sub = []
        for sp in pred.get("PredicateList", []):
            sub.append(extract_predicate(sp, ability))
        return "AllOf[" + " & ".join(sub) + "]"
    return f"{ptype}"


def extract_callback_config(cc: dict, ability: dict, mod_data: dict = None, indent: str = "          ") -> list[str]:
    """Extract CallbackConfig entries."""
    lines = []
    ttype = cc.get("$type", "")
    if ttype == "RPG.GameCore.PredicateTaskList":
        pred = cc.get("Predicate")
        if pred:
            pred_str = extract_predicate(pred, ability)
            lines.append(f"{indent}IF {pred_str}:")

        # SuccessTaskList
        stl = cc.get("SuccessTaskList", [])
        for task in stl:
            lines.extend(extract_task(task, ability, mod_data, indent + "  "))

        # FailedTaskList
        ftl = cc.get("FailedTaskList", [])
        if ftl:
            lines.append(f"{indent}ELSE:")
            for task in ftl:
                lines.extend(extract_task(task, ability, mod_data, indent + "  "))

        # ElseTaskList (some tasks have this)
        etl = cc.get("ElseTaskList", [])
        if etl:
            lines.append(f"{indent}ELSE:")
            for task in etl:
                lines.extend(extract_task(task, ability, mod_data, indent + "  "))

    else:
        # Direct action
        lines.extend(extract_task(cc, ability, mod_data, indent))

    return lines


def extract_ability(ability: dict) -> list[str]:
    """Extract all structured data for a single ability."""
    lines = []
    name = ability.get("Name", "Unknown")
    lines.append(f"=" * 80)
    lines.append(f"ABILITY: {name}")
    lines.append(f"=" * 80)
    lines.append("")

    # TargetType
    tgt = ability.get("TargetInfo", {}).get("TargetType", "?")
    lines.append(f"  TargetType: {tgt}")
    lines.append("")

    # DynamicValues summary
    dv = ability.get("DynamicValues", {}).get("Values", {})
    if dv:
        lines.append("  DynamicValues:")
        for hash_key, val_info in dv.items():
            dtype = val_info.get("ReadInfo", {}).get("Type", "?")
            lines.append(f"    {hash_key}: {dtype}")
        lines.append("")

    # OnStart actions
    onstart = ability.get("OnStart", [])
    if onstart:
        lines.append("  OnStart:")
        for action in onstart:
            atype = action.get("$type", "?")
            mod_name = action.get("ModifierName", "?")
            target = extract_target_alias(action.get("TargetType"))
            lines.append(f"    {atype}: {mod_name} → {target}")
            if "LifeTime" in action:
                lt = action["LifeTime"]
                if isinstance(lt, dict):
                    dv = resolve_dv_from_postfix(ability, lt.get("PostfixExpr"))
                    lines.append(f"      LifeTime: [DV: {dv}]")
                else:
                    lines.append(f"      LifeTime: {lt}")
            if "LifeStepMoment" in action:
                lines.append(f"      LifeStepMoment: {action['LifeStepMoment']}")
            if "Stacking" in action:
                lines.append(f"      Stacking: {action['Stacking']}")
        lines.append("")

    # Modifiers
    modifiers = ability.get("Modifiers", {})
    if modifiers:
        lines.append("  Modifiers:")
        for mod_name, mod_data in modifiers.items():
            lines.append(f"    [{mod_name}]")

            # Modifier-level properties
            stacking = mod_data.get("Stacking")
            if stacking:
                lines.append(f"      Stacking: {stacking}")
            max_layer = mod_data.get("MaxLayer")
            if max_layer is not None:
                lines.append(f"      MaxLayer: {max_layer}")
            layer_add = mod_data.get("LayerAddWhenStack")
            if layer_add is not None:
                if isinstance(layer_add, dict) and layer_add.get("FixedValue"):
                    lines.append(f"      LayerAddWhenStack: {layer_add['FixedValue'].get('Value', layer_add)}")
                else:
                    lines.append(f"      LayerAddWhenStack: {layer_add}")
            lifetime = mod_data.get("LifeTime")
            if lifetime is not None:
                if isinstance(lifetime, dict):
                    dv = resolve_dv_from_postfix(ability, lifetime.get("PostfixExpr"))
                    lines.append(f"      LifeTime: [DV: {dv}]")
                else:
                    lines.append(f"      LifeTime: {lifetime}")
            life_step = mod_data.get("LifeStepMoment")
            if life_step is not None:
                lines.append(f"      LifeStepMoment: {life_step}")
            bflags = mod_data.get("BehaviorFlagList")
            if bflags:
                lines.append(f"      BehaviorFlags: {bflags}")
            use_snapshot = mod_data.get("UseSnapshotEntity")
            if use_snapshot is not None:
                lines.append(f"      UseSnapshotEntity: {use_snapshot}")
            perform_time = mod_data.get("PerformTime")
            if perform_time is not None:
                if isinstance(perform_time, dict) and perform_time.get("FixedValue"):
                    lines.append(f"      PerformTime: {perform_time['FixedValue'].get('Value', perform_time)}")
                else:
                    lines.append(f"      PerformTime: {perform_time}")
            task_tpl = mod_data.get("TaskListTemplate")
            if task_tpl:
                if isinstance(task_tpl, list):
                    for tpl in task_tpl:
                        tname = tpl.get("Name", "?")
                        tcount = len(tpl.get("TaskList", []))
                        lines.append(f"      TaskListTemplate: {tname} ({tcount} tasks)")
                else:
                    lines.append(f"      TaskListTemplate: {task_tpl}")
            on_ability = mod_data.get("OnAbilityPropertyChange")
            if on_ability is not None:
                lines.append(f"      OnAbilityPropertyChange: present")
            preshow = mod_data.get("ModifierAffectedPreshowConfig")
            if preshow:
                if isinstance(preshow, dict):
                    skill_types = preshow.get("SkillTypes", [])
                    lines.append(f"      PreshowConfig: SkillTypes={skill_types}")
                else:
                    lines.append(f"      PreshowConfig: present")

            # Modifier DynamicValues
            mod_dv = mod_data.get("DynamicValues", {}).get("Values", {})
            if mod_dv:
                lines.append(f"      Modifier DynamicValues:")
                for dvk, dv_info in mod_dv.items():
                    dtype = dv_info.get("ReadInfo", {}).get("Type", "?")
                    lines.append(f"        {dvk}: {dtype}")

            # CallbackList
            cbl = mod_data.get("_CallbackList", [])
            if cbl:
                has_destroy = False
                for cb in cbl:
                    event = cb.get("Event", "?")
                    if event == "OnDestroy":
                        has_destroy = True
                    priority = cb.get("Priority")
                    lines.append(f"      Event: {event}" + (f" [Priority: {priority}]" if priority is not None else ""))
                    for cc in cb.get("CallbackConfig", []):
                        lines.extend(extract_callback_config(cc, ability, mod_data))
                if not has_destroy:
                    lines.append(f"      (No OnDestroy)")
            else:
                lines.append(f"      (No _CallbackList — empty modifier)")
            lines.append("")

    return lines


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ability_list = data.get("AbilityList", [])
    print(f"Total abilities in file: {len(ability_list)}")

    filtered = [a for a in ability_list if a["Name"].startswith("Ability2")]

    name_sort = sorted(filtered, key=lambda a: a["Name"])
    print(f"Extracting {len(name_sort)} abilities (Ability20000-24999 range)")
    print()

    # For readability, we'll output to a file
    output_lines = []
    for ab in name_sort:
        output_lines.extend(extract_ability(ab))

    output = "\n".join(output_lines)
    out_path = r"E:\starail_trial\scripts\equipment_abilities_extracted.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Output written to: {out_path}")
    print(f"Total lines: {len(output_lines)}")

    # Also print a summary
    print(f"\n{'=' * 80}")
    print("SUMMARY TABLE")
    print(f"{'=' * 80}")
    print(f"{'Ability':<15} {'TargetType':<15} {'#Modifiers':>10} {'Events':<50}")
    print("-" * 95)
    for ab in name_sort:
        tgt = ab.get("TargetInfo", {}).get("TargetType", "?")
        mods = ab.get("Modifiers", {})
        mod_count = len(mods)
        events = []
        for mn, md in mods.items():
            for cb in md.get("_CallbackList", []):
                ev = cb.get("Event", "?")
                if ev not in events:
                    events.append(ev)
        ev_str = ", ".join(events) if events else "(empty)"
        print(f"{ab['Name']:<15} {tgt:<15} {mod_count:>10} {ev_str:<50}")


if __name__ == "__main__":
    main()
