-- Shortcode: {{< revisions >}}
--
-- Renders the document's front-matter `revisions:` list as an
-- engineering-style revision block (Rev | Date | Author | Approved by |
-- Description). Used by the SOPs in chapters/03-operation/sops/:
--
--   revisions:
--     - rev: A
--       date: 2026-06-12
--       author: Ammar Barbee
--       approved-by: ""
--       description: Initial release
--
-- The table is built by round-tripping markdown through pandoc.read so
-- it renders in every book format (HTML + PDF). An empty or missing
-- list renders nothing. This is the manual sign-off record; the
-- auto-generated git change history (_revisions-<stem>.md) is separate.

local function cell(value)
  if value == nil then
    return ""
  end
  return pandoc.utils.stringify(value):gsub("|", "\\|")
end

function revisions(args, kwargs, meta)
  local revs = meta["revisions"]
  if revs == nil or #revs == 0 then
    return pandoc.Blocks({})
  end
  local lines = {
    "| Rev | Date | Author | Approved by | Description |",
    "|---|---|---|---|---|",
  }
  for _, rev in ipairs(revs) do
    lines[#lines + 1] = "| " .. cell(rev["rev"])
        .. " | " .. cell(rev["date"])
        .. " | " .. cell(rev["author"])
        .. " | " .. cell(rev["approved-by"])
        .. " | " .. cell(rev["description"]) .. " |"
  end
  local doc = pandoc.read(table.concat(lines, "\n"), "markdown")
  return doc.blocks
end

return {
  ["revisions"] = revisions,
}
