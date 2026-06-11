local SkillSystem = {}
SkillSystem.__index = SkillSystem

function SkillSystem:new()
    local obj = { cooldowns = {}, active_effects = {} }
    setmetatable(obj, self)
    return obj
end

function SkillSystem:cast_skill(caster, skill_id, target)
    local skill = self.skills[skill_id]
    if not skill then return false end

    -- Apply damage
    self:apply_damage(caster, target, skill.base_damage)

    -- Apply effect
    if skill.effect then
        self:apply_effect(target, skill.effect)
    end

    return true
end

function SkillSystem:apply_damage(caster, target, amount)
    target.hp = target.hp - amount
    -- trigger event
    self:on_damage_dealt(caster, target, amount)
end

return SkillSystem
