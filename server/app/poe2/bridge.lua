-- Data-only, one-build-per-process adapter to the pinned upstream PoB runtime.
local json = require('dkjson')
local function read(path)
    local file = assert(io.open(path, 'rb'))
    local content = file:read('*a')
    file:close()
    return content
end
local input = assert(json.decode(read(assert(os.getenv('POE2_INPUT')))))
local treeView = dofile(arg[0]:gsub('bridge.lua$', 'tree_view.lua'))
local function execute()
    dofile('HeadlessWrapper.lua')
    -- Upstream headless stubs are suitable for tests, but export/compressed data
    -- need real zlib. The Python boundary handles share-code compression.
    local zlib = require('zlib')
    Deflate = function(data) return zlib.deflate()(data, 'finish') end
    Inflate = function(data) return zlib.inflate()(data) end
    assert(build and build.calcsTab, 'POE2_ENGINE_INIT_FAILED')
    loadBuildFromXML(input.xml, 'Chickenbro')
    assert(build and build.calcsTab and build.calcsTab.mainOutput, 'POE2_BUILD_LOAD_FAILED')
    local changes = input.changes or {}
    if changes.level then
        build.characterLevel = changes.level
        build.characterLevelAutoMode = false
    end
    if changes.mainSocketGroup then
        assert(build.skillsTab.socketGroupList[changes.mainSocketGroup], 'POE2_SKILL_GROUP_INVALID')
        build.mainSocketGroup = changes.mainSocketGroup
    end
    for _, candidate in ipairs(changes.skillGroups or {}) do
        local group = assert(build.skillsTab.socketGroupList[candidate.index], 'POE2_SKILL_GROUP_INVALID')
        local gems = {}
        for _, gem in ipairs(candidate.gems) do
            gems[#gems + 1] = {nameSpec = gem.name, level = gem.level, quality = gem.quality, enabled = true}
        end
        group.gemList = gems
        build.skillsTab:ProcessSocketGroup(group)
        for _, gem in ipairs(group.gemList) do
            assert(gem.gemData and not gem.errMsg, 'POE2_GEM_UNRECOGNIZED')
        end
    end
    for _, candidate in ipairs(changes.items or {}) do
        local item = new('Item', candidate.text)
        item:BuildAndParseRaw()
        assert(item.base, 'POE2_ITEM_UNRECOGNIZED')
        assert(build.itemsTab.slots[candidate.slot] and build.itemsTab:IsItemValidForSlot(item, candidate.slot), 'POE2_ITEM_SLOT_INVALID')
        build.itemsTab:AddItem(item, true)
        build.itemsTab.slots[candidate.slot]:SetSelItemId(item.id)
    end
    for _, id in ipairs(changes.deallocateNodes or {}) do
        local node = build.spec.nodes[id]
        assert(node and node.alloc and node.type ~= 'ClassStart', 'POE2_NODE_INVALID')
        build.spec:DeallocNode(node)
    end
    for _, id in ipairs(changes.allocateNodes or {}) do
        local node = build.spec.nodes[id]
        assert(node and not node.alloc and node.path and #node.path > 0, 'POE2_NODE_UNREACHABLE')
        build.spec:AllocNode(node)
        assert(node.alloc, 'POE2_NODE_NOT_APPLIED')
    end
    for key, value in pairs(changes.config or {}) do
        build.configTab.input[key] = value
    end
    build.configTab:BuildModList()
    build.buildFlag = true
    runCallback('OnFrame')
    if input.viewTree then return treeView(build) end
    local output = build.calcsTab.mainOutput
    local used, asc, secondary, _, weapon1, weapon2 = build.spec:CountAllocNodes()
    local pointLimit = build.characterLevel - 1 + build.maxWeaponSets + (output.ExtraPoints or 0)
    if changes.allocateNodes or changes.deallocateNodes then
        assert(used - math.min(weapon1, weapon2) <= pointLimit and asc <= 8 and secondary <= 8,
            'POE2_PASSIVE_POINTS_EXCEEDED')
    end
    local stats = {}
    for _, key in ipairs({'Str', 'Dex', 'Int', 'Spirit', 'Life', 'Mana', 'EnergyShield', 'CombinedDPS', 'TotalDPS', 'TotalDot', 'AverageDamage',
        'Speed', 'CritChance', 'CritMultiplier', 'HitChance', 'Armour', 'Evasion', 'BlockChance',
        'FireResist', 'ColdResist', 'LightningResist', 'ChaosResist', 'LifeRegen', 'EnergyShieldRegen',
        'TotalEHP', 'PhysicalMaximumHitTaken', 'FireMaximumHitTaken', 'ColdMaximumHitTaken',
        'LightningMaximumHitTaken', 'ChaosMaximumHitTaken', 'ManaRegen'}) do
        local value = output[key]
        if type(value) == 'number' and value == value and math.abs(value) < math.huge then
            stats[key] = value
        end
    end
    local config, skills, items, nodes, unsupported = setmetatable({}, {__jsontype = 'object'}), {}, {}, {}, {}
    for _, warning in ipairs(build.controls.warnings.lines or {}) do
        unsupported[#unsupported + 1] = warning
    end
    if used - math.min(weapon1, weapon2) > pointLimit then
        unsupported[#unsupported + 1] = 'Passive points exceed level budget (all quest rewards assumed)'
    end
    for key, value in pairs(build.configTab.input or {}) do
        if type(value) == 'number' or type(value) == 'string' or type(value) == 'boolean' then
            config[key] = value
        end
    end
    for index, group in ipairs(build.skillsTab.socketGroupList or {}) do
        local gems = {}
        for _, gem in ipairs(group.gemList or {}) do
            gems[#gems + 1] = {name = gem.nameSpec or gem.name or '', level = gem.level, quality = gem.quality, enabled = gem.enabled}
            if not gem.gemData then unsupported[#unsupported + 1] = 'Unrecognized gem: ' .. (gem.nameSpec or '?') end
        end
        skills[#skills + 1] = {index = index, label = group.label or '', gems = gems}
    end
    for _, slot in ipairs(build.itemsTab.orderedSlots) do
        local item = build.itemsTab.items[slot.selItemId]
        if item then
            items[#items + 1] = {slot = slot.slotName, name = item.name or item.baseName, text = item.raw}
            for _, list in ipairs({item.explicitModLines or {}, item.implicitModLines or {}, item.enchantModLines or {}}) do
                for _, line in ipairs(list) do
                    if line.extra or not line.modList then unsupported[#unsupported + 1] = slot.slotName .. ': ' .. (line.line or '?') end
                end
            end
        end
    end
    for id, node in pairs(build.spec.nodes) do
        if node.alloc then nodes[#nodes + 1] = id end
    end
    table.sort(nodes)
    local xml = assert(build:SaveDB('code'), 'POE2_EXPORT_FAILED')
    return {stats = stats, summary = {level = build.characterLevel, className = build.spec.curClassName,
        ascendancy = build.spec.curAscendClassName, treeVersion = build.spec.treeVersion},
        effectiveConfig = config, mainSocketGroup = build.mainSocketGroup, skills = skills,
        items = items, allocatedNodes = nodes, unsupported = unsupported, exportXml = xml,
        scope = 'configured_theoretical_calculation'}
end
local ok, result = pcall(execute)
if not ok then
    local code = tostring(result):match('POE2_[A-Z_]+') or 'POE2_ENGINE_FAILED'
    io.stderr:write(tostring(result), '\n')
    result = {error = code}
end
local file = assert(io.open(assert(os.getenv('POE2_OUTPUT')), 'w'))
file:write(json.encode(result))
file:close()
