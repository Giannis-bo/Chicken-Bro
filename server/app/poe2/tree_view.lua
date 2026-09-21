-- Read-only projection of the engine's effective spec. Never reconstruct allocation
-- from the flat XML list: weapon sets, attribute choices and jewels live on spec.
local function arcFor(a, b, connection, tree)
    local cx, cy, r
    local orbit = math.abs(connection.orbit or 0)
    if orbit > 0 and tree.orbitRadii[orbit + 1] then
        r = tree.orbitRadii[orbit + 1] * tree.scaleImage
        local dx, dy = b.x - a.x, b.y - a.y
        local dist = math.sqrt(dx * dx + dy * dy)
        if dist == 0 or dist >= 2 * r then return nil end
        local perp = math.sqrt(r * r - dist * dist / 4) * (connection.orbit > 0 and 1 or -1)
        cx = a.x + dx / 2 + perp * dy / dist
        cy = a.y + dy / 2 - perp * dx / dist
    elseif a.g == b.g and a.o == b.o and a.group and a.o > 0 then
        cx, cy = a.group.x * tree.scaleImage, a.group.y * tree.scaleImage
        r = tree.orbitRadii[a.o + 1] * tree.scaleImage
    else return nil end
    local first, last = math.atan2(a.y - cy, a.x - cx), math.atan2(b.y - cy, b.x - cx)
    local delta = (last - first + math.pi) % (2 * math.pi) - math.pi
    return {x = cx, y = cy, radius = r, start = first, sweep = delta}
end

return function(build)
    local spec = build.spec
    local nodes, edges, present, seen = {}, {}, {}, {}
    for id, node in pairs(spec.nodes) do
        if node.x and node.y and node.type ~= 'OnlyImage' then
            local stats = {}
            for _, line in ipairs(node.sd or {}) do stats[#stats + 1] = line end
            local size = node.targetSize and node.targetSize.width or 40
            nodes[#nodes + 1] = {id = id, x = node.x, y = node.y,
                name = node.dn or node.name or '', stats = stats, type = node.type or 'Normal',
                ascendancy = node.ascendancyName or '', allocated = node.alloc == true,
                allocation = node.allocMode or 0, icon = node.icon or '', size = size}
            present[id] = true
        end
    end
    for id, node in pairs(spec.nodes) do
        if present[id] then
            for _, connection in ipairs(node.connections or {}) do
                local other = spec.nodes[connection.id]
                if other and present[other.id] and id ~= other.id and node.ascendancyName == other.ascendancyName then
                    local key = math.min(id, other.id)..':'..math.max(id, other.id)
                    if not seen[key] then
                        seen[key] = true
                        edges[#edges + 1] = {from = id, to = other.id, arc = arcFor(node, other, connection, spec.tree)}
                    end
                end
            end
        end
    end
    table.sort(nodes, function(a, b) return a.id < b.id end)
    return {treeVersion = spec.treeVersion, className = spec.curClassName,
        ascendancy = spec.curAscendClassName or '', secondaryAscendancy = spec.curSecondaryAscendClassName or '',
        nodes = nodes, edges = edges}
end
