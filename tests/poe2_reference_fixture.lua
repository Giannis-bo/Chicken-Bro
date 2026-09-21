-- Independent direct-upstream fixture generator. Run only on the cloud host.
-- These are synthetic builds, not player snapshots or gameplay acceptance.
dofile('HeadlessWrapper.lua')
local json = require('dkjson')
local directory = assert(os.getenv('POE2_FIXTURE_DIR'))
local cases = {'Fireball', 'Spark', 'Raise Zombie'}
for index, skill in ipairs(cases) do
    newBuild()
    build.characterLevel = 90
    build.characterLevelAutoMode = false
    build.skillsTab:PasteSocketGroup(skill .. ' 20/0  1')
    build.mainSocketGroup = 1
    build.buildFlag = true
    runCallback('OnFrame')
    local xml = assert(build:SaveDB('code'))
    local file = assert(io.open(directory .. '/build-' .. index .. '.xml', 'w'))
    file:write(xml)
    file:close()
    local stats = {}
    for _, key in ipairs({'Life', 'Mana', 'EnergyShield', 'CombinedDPS', 'TotalDPS', 'FireResist', 'ColdResist', 'LightningResist', 'ChaosResist'}) do
        stats[key] = build.calcsTab.mainOutput[key]
    end
    local baseline = assert(io.open(directory .. '/build-' .. index .. '.json', 'w'))
    local reachable
    for id, node in pairs(build.spec.nodes) do
        if not node.alloc and node.path and #node.path == 1 and not node.ascendancyName then
            if not reachable or id < reachable then reachable = id end
        end
    end
    baseline:write(json.encode({skill = skill, stats = stats, reachableNode = reachable}))
    baseline:close()
end
