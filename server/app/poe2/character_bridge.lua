-- Native import only; input paths are chosen by the Python worker.
local json = require('dkjson')
local file = assert(io.open(assert(os.getenv('POE2_INPUT')), 'rb'))
local character = assert(json.decode(file:read('*a')))
file:close()
local function execute()
    dofile('HeadlessWrapper.lua')
    local zlib = require('zlib')
    Deflate = function(data) return zlib.deflate()(data, 'finish') end
    Inflate = function(data) return zlib.inflate()(data) end
    newBuild()
    local expectedGems = {}
    for _, id in ipairs(character._mapping.expected_gem_ids) do
        expectedGems[id] = (expectedGems[id] or 0) + 1
    end
    local verifiedGems = {}
    local function checkGem(gem)
        local key = gem.typeLine .. (gem.support and ' Support' or '')
        local id = assert(build.data.gemForBaseName[key:lower()], 'POE2_GEM_UNMAPPED')
        assert(expectedGems[id], 'POE2_GEM_ID_MISMATCH')
        verifiedGems[id] = (verifiedGems[id] or 0) + 1
        for _, child in ipairs(gem.socketedItems or {}) do checkGem(child) end
    end
    for _, gem in ipairs(character.skills) do checkGem(gem) end
    for id, count in pairs(expectedGems) do
        assert(verifiedGems[id] == count, 'POE2_GEM_ID_MISMATCH')
    end
    for _, item in ipairs(character.equipment) do
        assert(build.data.itemBases[item.typeLine], 'POE2_BASE_UNMAPPED')
        for _, kind in ipairs({'implicitMods', 'explicitMods', 'enchantMods', 'runeMods', 'craftedMods', 'fracturedMods', 'desecratedMods', 'mutatedMods'}) do
            for _, raw in ipairs(item[kind] or {}) do
                local line = type(raw) == 'table' and raw.description or raw
                local mods, extra = modLib.parseMod(line)
                assert(mods and #mods > 0 and not extra, 'POE2_MOD_UNPARSED')
            end
        end
    end
    build.importTab.controls.charImportItemsIgnoreWeaponSwap.state = false
    build.importTab:ImportPassiveTreeAndJewels(character)
    build.importTab:ImportItemsAndSkills(character)
    -- Native ImportTab estimates progression from level; replace with attested input.
    build.configTab.input.resistancePenalty = assert(character._mapping.resistance_penalty)
    build.configTab:BuildModList()
    build.buildFlag = true
    runCallback('OnFrame')
    local itemCount = 0
    for _, item in pairs(build.itemsTab.items) do
        itemCount = itemCount + 1
        assert(item.base, 'POE2_ITEM_DROPPED')
    end
    assert(itemCount == #character.equipment + #character.jewels, 'POE2_ITEM_COUNT_MISMATCH')
    assert(#build.skillsTab.socketGroupList == #character.skills, 'POE2_SKILL_COUNT_MISMATCH')
    local gemCount = 0
    for _, group in ipairs(build.skillsTab.socketGroupList) do
        for _, gem in ipairs(group.gemList) do
            assert(gem.gemData and expectedGems[gem.gemId] and expectedGems[gem.gemId] > 0, 'POE2_GEM_DROPPED')
            expectedGems[gem.gemId] = expectedGems[gem.gemId] - 1
            gemCount = gemCount + 1
        end
    end
    assert(gemCount == character._mapping.expected_gems, 'POE2_GEM_COUNT_MISMATCH')
    local function checkNodes(nodes, mode)
        for _, id in ipairs(nodes) do
            assert(build.spec.nodes[id] and build.spec.nodes[id].alloc, 'POE2_NODE_DROPPED')
            assert(build.spec.nodes[id].allocMode == mode, 'POE2_WEAPON_SET_MISMATCH')
        end
    end
    checkNodes(character.passives.hashes, 0)
    for name, nodes in pairs(character.passives.specialisations) do checkNodes(nodes, tonumber(name:sub(4))) end
    for id, choice in pairs(character.passives.skill_overrides) do
        assert(build.spec.nodes[tonumber(id)].dn == choice.name, 'POE2_ATTRIBUTE_MISMATCH')
    end
    local xml = assert(build:SaveDB('code'), 'POE2_EXPORT_FAILED')
    return {xml = xml}
end
local ok, result = pcall(execute)
if not ok then io.stderr:write(tostring(result)); result = {error = 'POE2_CHARACTER_CONVERSION_FAILED'} end
local output = assert(io.open(assert(os.getenv('POE2_OUTPUT')), 'w'))
output:write(json.encode(result))
output:close()
